from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import NullPool
from config import DATABASE_URL

# Use the database provider's pooler (e.g. Supabase transaction pooler).
# Do not multiply persistent connection pools across serverless instances.
engine = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    # Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
