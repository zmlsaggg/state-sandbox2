"""Distributed admission control and authenticated browser result delivery."""
import os
import time
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import case, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import get_db, SessionLocal
from db.models import AIBudget, AIResult, User
from model.ai_session import AISession, current_ai
from routers.auth import get_current_user_from_token

router = APIRouter(prefix='/api/ai', tags=['ai'])
DEFAULT_MODELS = {
    'puter': 'gpt-4o-mini', 'openai': 'gpt-4o-mini',
    'groq': 'llama-3.3-70b-versatile', 'openrouter': 'openai/gpt-4o-mini',
}
WINDOW = int(os.getenv('AI_RATE_WINDOW_SECONDS', '600'))
LIMIT = int(os.getenv('AI_RATE_ACTIONS', '12'))
COOLDOWN = int(os.getenv('AI_COOLDOWN_SECONDS', '8'))
LEASE = int(os.getenv('AI_ACTION_LEASE_SECONDS', '330'))


if LIMIT < 1 or WINDOW < 1 or COOLDOWN < 0:
    raise ValueError('AI rate limits must be positive, with a non-negative cooldown.')
if LEASE <= max(300, int(os.getenv('STREAM_TIMEOUT_SECONDS', '280'))):
    raise ValueError('AI_ACTION_LEASE_SECONDS must exceed the platform/stream timeout.')


def budget_status(budget, now):
    expired = budget is None or budget.window_start <= now - WINDOW
    used = 0 if expired else budget.count
    active_for = max(0, budget.active_until - now) if budget else 0
    cooldown_for = max(0, budget.last_started + COOLDOWN - now) if budget else 0
    reset_in = max(0, budget.window_start + WINDOW - now) if budget and not expired else 0
    return {
        'limits': {'actions': LIMIT, 'window_seconds': WINDOW, 'cooldown_seconds': COOLDOWN},
        'remaining_actions': max(0, LIMIT - used),
        'active': active_for > 0,
        'retry_after_seconds': max(active_for, cooldown_for, reset_in if used >= LIMIT else 0),
        'reset_in_seconds': reset_in,
    }


@router.get('/status')
def get_ai_status(response: Response,
                  user: User = Depends(get_current_user_from_token),
                  db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return budget_status(db.get(AIBudget, user.id), int(time.time()))


def acquire(db, user_id):
    now = int(time.time())
    # Insert once; concurrent first actions are serialized by the primary key.
    try:
        with db.begin_nested():
            db.add(AIBudget(user_id=user_id))
            db.flush()
    except IntegrityError:
        pass
    expired = AIBudget.window_start <= now - WINDOW
    owner = str(uuid4())
    updated = db.query(AIBudget).filter(
        AIBudget.user_id == user_id,
        AIBudget.active_until <= now,
        AIBudget.last_started <= now - COOLDOWN,
        or_(expired, AIBudget.count < LIMIT),
    ).update({
        AIBudget.window_start: case((expired, now), else_=AIBudget.window_start),
        AIBudget.count: case((expired, 1), else_=AIBudget.count + 1),
        AIBudget.last_started: now, AIBudget.active_until: now + LEASE,
        AIBudget.owner: owner,
    }, synchronize_session=False)
    db.commit()
    if not updated:
        budget = db.get(AIBudget, user_id)
        retry = max(1, budget_status(budget, now)['retry_after_seconds'])
        raise HTTPException(429, 'AI action already active or rate limit reached. Please wait.',
                            headers={'Retry-After': str(retry)})
    return owner


def release(db, user_id, owner):
    db.query(AIBudget).filter_by(user_id=user_id, owner=owner).update(
        {AIBudget.active_until: 0, AIBudget.owner: None}, synchronize_session=False)
    db.commit()


async def ai_session(
    user: User = Depends(get_current_user_from_token),
    provider: str = Header('', alias='X-AI-Provider'),
    key: str = Header('', alias='X-AI-Key'),
    model: str = Header('', alias='X-AI-Model'),
):
    if provider not in DEFAULT_MODELS:
        raise HTTPException(400, 'Connect Puter or your own AI key in Account settings.')
    if provider != 'puter' and (not key.strip() or len(key) > 4096):
        raise HTTPException(400, 'A personal provider API key is required.')
    model = model.strip() or DEFAULT_MODELS[provider]
    if len(model) > 160 or any(ord(c) < 32 for c in model):
        raise HTTPException(400, 'Invalid model name.')
    # Independent short-lived DB sessions: never hold a connection during AI work.
    with SessionLocal() as db:
        owner = acquire(db, user.id)
        db.query(AIResult).filter(AIResult.expires_at < datetime.now(timezone.utc)).delete()
        db.commit()
    token = current_ai.set(AISession(user.id, provider, model, key.strip()))
    try:
        yield current_ai.get()
    finally:
        current_ai.reset(token)
        with SessionLocal() as db:
            release(db, user.id, owner)


class BrowserResult(BaseModel):
    content: str = Field(default='', max_length=500_000)
    error: bool = False


@router.post('/results/{request_id}', status_code=204)
def deliver_result(request_id: str, result: BrowserResult,
                   user: User = Depends(get_current_user_from_token),
                   db: Session = Depends(get_db)):
    updated = db.query(AIResult).filter(
        AIResult.id == request_id, AIResult.user_id == user.id,
        AIResult.expires_at > datetime.now(timezone.utc), AIResult.content.is_(None),
    ).update({AIResult.content: result.content, AIResult.error: result.error},
             synchronize_session=False)
    db.commit()
    if not updated:
        raise HTTPException(404, 'AI request expired, already answered, or not found.')
