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
    One row per combined alert created by system
    (for parent dashboard)
    """
    __tablename__ = "alert"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, index=True, nullable=False)
    explanation = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    timestamp = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)

# function to create tables.
def init_db():
    Base.metadata.create_all(bind=engine)

# helper to get a db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()