"""Request-local credentials. Never persisted and never fall back to owner keys."""
from contextvars import ContextVar
from dataclasses import dataclass, field
import asyncio
import os


@dataclass
class AISession:
    user_id: int
    provider: str
    model: str
    key: str = field(default='', repr=False)
    slots: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(max(1, int(os.getenv('AI_MAX_PARALLEL_CALLS', '3')))))
    events: asyncio.Queue = field(default_factory=asyncio.Queue)


current_ai: ContextVar[AISession] = ContextVar('current_ai')


class AIError(Exception):
    """Safe public error, containing no upstream response or credentials."""
