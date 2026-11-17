"""Personal-key API calls or browser Puter relay; no owner-funded fallback."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from openai import AsyncOpenAI, APIError, APITimeoutError
from db.database import SessionLocal
from db.models import AIResult
from model.ai_session import current_ai, AIError

ENDPOINTS = {
    'openai': 'https://api.openai.com/v1',
    'groq': 'https://api.groq.com/openai/v1',
    'openrouter': 'https://openrouter.ai/api/v1',
}


class OpenAIProvider:
    # Retain the name/interface used by all existing game actions.
    async def _generate(self, text):
        session = current_ai.get(None)
        if session is None:
            raise AIError('Connect your AI provider in Account settings.')
        async with session.slots:
            return await self._call(text, session)

    async def _call(self, text, session):
        if session.provider == 'puter':
            return await self._browser(text, session)
        try:
            async with AsyncOpenAI(api_key=session.key, base_url=ENDPOINTS[session.provider],
                                   timeout=90, max_retries=0) as client:
                response = await client.chat.completions.create(
                    model=session.model, messages=[{'role': 'user', 'content': text}],
                )
            content = response.choices[0].message.content
            if not content or len(content) > 500_000:
                raise AIError('AI returned empty or oversized output. Try another model.')
            return content
        except APITimeoutError:
            raise AIError('Your AI provider timed out. Please retry.') from None
        except APIError as exc:
            status = getattr(exc, 'status_code', None)
            if status in (401, 403):
                message = 'Your AI key was rejected. Check Account settings.'
            elif status in (402, 429):
                message = 'Your AI account has reached its quota or billing limit.'
            else:
                message = 'Your AI provider is unavailable or does not support this model.'
            raise AIError(message) from None

    async def _browser(self, text, session):
        request_id = str(uuid4())
        with SessionLocal() as db:
            db.add(AIResult(id=request_id, user_id=session.user_id,
                            expires_at=datetime.now(timezone.utc) + timedelta(seconds=270)))
            db.commit()
        try:
            await session.events.put({'type': 'ai_request', 'request_id': request_id,
                                      'prompt': text, 'model': session.model})
            async with asyncio.timeout(265):
                while True:
                    await asyncio.sleep(0.5)
                    with SessionLocal() as db:
                        row = db.get(AIResult, request_id)
                        if row is None:
                            raise AIError('AI request expired. Please retry.')
                        if row.content is not None:
                            if row.error or not row.content.strip():
                                raise AIError('Puter could not complete this request. Check your connection, model and account quota.')
                            return row.content
        except TimeoutError:
            raise AIError('Puter request timed out. Keep the game tab open and retry.') from None
        finally:
            with SessionLocal() as db:
                db.query(AIResult).filter_by(id=request_id).delete()
                db.commit()

    async def generate_medium_reasoning(self, text: str) -> str:
        return await self._generate(text)

    async def generate_high_reasoning(self, text: str) -> str:
        return await self._generate(text)

    async def generate_low_reasoning(self, text: str) -> str:
        return await self._generate(text)
