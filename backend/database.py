from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timezone

# Database connection.
DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread":False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False,bind=engine)

Base = declarative_base()

# TABLES.
class Child(Base):
    """Tabel: Children - One row per-child monitoring."""
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, unique=True, index=True, nullable=False)
    monitoring_status = Column(String, default="on")
    created_at = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)

class Event(Base):
    """
    Tabel: Event - one row : raw data recived from browser..
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False) # url or text
    content = Column(String, nullable=False) # actual url or text
    risk_label = Column(String, nullable=True)
    risk_confidence = Column(String, nullable=True)
    timestamp = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)

class Alert(Base):
    """
    Table: Alert
    One row per ONGOING pattern of concern for a child (for parent dashboard).

    Instead of inserting a brand-new row every time new risky events keep
    matching the same pattern, the correlation engine UPDATES this row in
    place (new explanation covering everything, refreshed timestamp) while
    the pattern is still "current". This is what keeps the parent looking
    at one clear, evolving explanation instead of a flood of near-duplicate
    alerts for the same underlying situation.
    """
    __tablename__ = "alert"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, index=True, nullable=False)
    explanation = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    pattern_type = Column(String, nullable=False, default="short_term")  # "short_term" or "long_term"
    event_count = Column(Integer, nullable=False, default=0)  # how many risky events this alert currently covers
    timestamp = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default= lambda: datetime.now(timezone.utc), onupdate= lambda: datetime.now(timezone.utc), index=True)

# function to create tables.
def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()

def _migrate_add_missing_columns():
    """
    Lightweight migration for people (like us, mid-dev) who already have a
    database.db from before these columns existed. SQLite supports simple
    ADD COLUMN, so we just check what's there and patch it up instead of
    forcing everyone to delete their test database.
    """
    with engine.connect() as conn:
        existing_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(alert)")}
        if "pattern_type" not in existing_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN pattern_type VARCHAR DEFAULT 'short_term'")
        if "event_count" not in existing_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN event_count INTEGER DEFAULT 0")
        if "updated_at" not in existing_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN updated_at DATETIME")
        conn.commit()

# helper to get a db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()