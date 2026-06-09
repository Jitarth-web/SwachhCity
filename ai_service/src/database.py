"""
Database configuration for AI Service.
IEEE Std 830-1998 SRS compliant database layer.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from shared.utils import settings

# Database configuration
DATABASE_URL = settings.DATABASE_URL or "postgresql://swachh_user:swachh_pass@localhost:5432/swachhgram"

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=os.getenv("DEBUG", "false").lower() == "true"
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base model class
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
