"""Run before rollout: PYTHONPATH=. python scripts/init_ai_tables.py"""
from sqlalchemy import text
from db.database import engine
from db.models import AIBudget, AIResult

def init_ai_tables():
    # Additive only. Existing game tables/credits/snapshots are untouched.
    AIBudget.__table__.create(engine, checkfirst=True)
    AIResult.__table__.create(engine, checkfirst=True)
    if engine.dialect.name == 'postgresql':
        # Browser relay data must not be exposed through public REST DB adapters.
        # The trusted backend must connect as table owner or a BYPASSRLS role.
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE ai_budgets ENABLE ROW LEVEL SECURITY'))
            connection.execute(text('ALTER TABLE ai_results ENABLE ROW LEVEL SECURITY'))


if __name__ == '__main__':
    init_ai_tables()
