from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from config import CREDITS_DEFAULT
from db.database import Base


class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    credits = Column(Integer, nullable=False, default=CREDITS_DEFAULT)
    states = relationship("State", back_populates="user")


class State(TimestampMixin, Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)  # Format: YYYY-MM
    flag_svg = Column(String, nullable=False)
    description = Column(String, nullable=False)
    turn_in_progress = Column(Boolean, nullable=False, default=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="states")
    snapshots = relationship("StateSnapshot", back_populates="state")


class StateSnapshot(TimestampMixin, Base):
    __tablename__ = "state_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False)  # Format: YYYY-MM
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)

    markdown_state = Column(String, nullable=False)
    markdown_future_events = Column(String, nullable=False)
    markdown_future_events_policy = Column(String, nullable=False)
    markdown_delta = Column(String, nullable=True)
    markdown_delta_report = Column(String, nullable=True)

    # Relationship to State
    state = relationship("State", back_populates="snapshots")


class AIResult(Base):
    """Short-lived browser relay mailbox, never contains provider credentials."""
    __tablename__ = "ai_results"
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    content = Column(String, nullable=True)
    error = Column(Boolean, nullable=False, default=False)


class AIBudget(Base):
    __tablename__ = "ai_budgets"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    # Epoch seconds keep conditional updates identical on Postgres and test SQLite.
    window_start = Column(Integer, nullable=False, default=0)
    count = Column(Integer, nullable=False, default=0)
    last_started = Column(Integer, nullable=False, default=0)
    active_until = Column(Integer, nullable=False, default=0)
    owner = Column(String(36), nullable=True)
