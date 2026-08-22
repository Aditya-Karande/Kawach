from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, timezone

# Database connection.
DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread":False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False,bind=engine)

Base = declarative_base()

# SQLite's DateTime column silently drops tzinfo, even though every model
# below writes datetime.now(timezone.utc). So a timestamp that's actually
# UTC comes back out of the DB "naive", and FastAPI serializes it without
# a `Z`/offset (e.g. "2026-08-22T10:46:00"). The browser's `new Date(...)`
# then has no way to know it's UTC and renders it as raw local time —
# for an IST user that's a silent 5:30 hr shift (this is the "alert says
# 10:40 AM but was actually 4:16 PM" bug). Stamp it back to UTC on the way
# out so the ISO string always carries an explicit offset.
def to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()

# TABLES.

class Parent(Base):
    """Table: parents — the account that owns children + receives alerts."""
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    children = relationship("Child", back_populates="parent")


class Child(Base):
    """Tabel: Children - One row per-child monitoring."""
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, unique=True, index=True, nullable=False)
    # Display info for the parent dashboard's child-switcher screen
    # (e.g. "Aarav, Age 12"). child_id itself stays a separate, stable
    # identifier used everywhere else (events, alerts, pairing) so
    # renaming a child later never breaks existing data.
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=True, index=True)
    monitoring_status = Column(String, default="on")
    pairing_code = Column(String, unique=True, index=True, nullable=True)
    # Per-child multiplier applied to signal weights, adjusted by the
    # feedback loop (Section 7.1) when a parent marks an alert "not a
    # concern". Defaults to 1.0 (no adjustment).
    weight_multiplier = Column(Float, default=1.0)
    created_at = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)

    parent = relationship("Parent", back_populates="children")
    guardians = relationship("Guardian", back_populates="child")


class Guardian(Base):
    """Table: guardians — optional second contact for tier-3 alerts (Section 7.3)."""
    __tablename__ = "guardians"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False, index=True)
    email = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    child = relationship("Child", back_populates="guardians")


class Event(Base):
    """
    Tabel: Event - one row : raw data recived from browser..
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    # signal_type: search_query | url_visit | page_text | chat_text
    signal_type = Column(String, nullable=False)
    content = Column(String, nullable=False) # actual url or text
    risk_label = Column(String, nullable=True)
    risk_confidence = Column(String, nullable=True)
    # Point value assigned at ingest time (see core/scoring.py). The
    # correlation engine sums this column instead of counting rows.
    weight = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)


class Alert(Base):
    """
    Table: Alert
    One row per tier-3 (high) scored cluster of signals for a child, for
    the parent dashboard. Tiers 1/2 never create a row here — tier 1 is
    logged silently via Event.weight alone, tier 2 is a nudge shown to the
    child (still just an Event row), only tier 3 pushes something to the
    parent and gets an Alert row + AI explanation.
    """
    __tablename__ = "alert"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(String, index=True, nullable=False)
    tier = Column(Integer, nullable=False, default=3)
    score = Column(Integer, nullable=False, default=0)
    # List of Event.id values that contributed to this alert's score —
    # powers the dashboard's expandable score breakdown (spec 7.2).
    contributing_signal_ids = Column(JSON, nullable=False, default=list)
    # {"what_happened": ..., "why_it_matters": ..., "recommended_action": ..., "severity_label": ...}
    ai_explanation = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="new")  # new | reviewed | dismissed

    # Kept from the v1 short-term/long-term model. No longer required by
    # the tier system, but harmless to keep around for now.
    pattern_type = Column(String, nullable=False, default="short_term")
    event_count = Column(Integer, nullable=False, default=0)

    timestamp = Column(DateTime, default= lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default= lambda: datetime.now(timezone.utc), onupdate= lambda: datetime.now(timezone.utc), index=True)


class Feedback(Base):
    """
    Table: feedback — a parent's verdict on an alert. Feeds the
    false-positive threshold multiplier (Section 7.1): repeated
    "not_a_concern" verdicts for a child raise that child's
    weight_multiplier divisor over time (see routes/alerts.py).
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alert.id"), nullable=False, index=True)
    parent_verdict = Column(String, nullable=False)  # reviewed | not_a_concern
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# function to create tables.
def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()

def _migrate_add_missing_columns():
    """
    Lightweight migration for people (like us, mid-dev) who already have a
    database.db from before these columns existed. SQLite supports simple
    ADD COLUMN (and, since 3.25, RENAME COLUMN), so we just check what's
    there and patch it up instead of forcing everyone to delete their test
    database.
    """
    with engine.connect() as conn:
        # --- events table ---
        event_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(events)")}
        if "signal_type" not in event_cols:
            if "type" in event_cols:
                conn.exec_driver_sql("ALTER TABLE events RENAME COLUMN type TO signal_type")
            else:
                conn.exec_driver_sql("ALTER TABLE events ADD COLUMN signal_type VARCHAR")
        if "session_id" not in event_cols:
            conn.exec_driver_sql("ALTER TABLE events ADD COLUMN session_id VARCHAR")
        if "weight" not in event_cols:
            conn.exec_driver_sql("ALTER TABLE events ADD COLUMN weight INTEGER DEFAULT 0")

        # --- alert table ---
        alert_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(alert)")}
        if "pattern_type" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN pattern_type VARCHAR DEFAULT 'short_term'")
        if "event_count" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN event_count INTEGER DEFAULT 0")
        if "updated_at" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN updated_at DATETIME")
        if "tier" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN tier INTEGER DEFAULT 3")
        if "score" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN score INTEGER DEFAULT 0")
        if "contributing_signal_ids" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN contributing_signal_ids JSON")
        if "ai_explanation" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN ai_explanation JSON")
        if "status" not in alert_cols:
            conn.exec_driver_sql("ALTER TABLE alert ADD COLUMN status VARCHAR DEFAULT 'new'")
        # Migrate legacy flat `explanation`/`risk_level` columns (if present)
        # into the new ai_explanation JSON shape so old rows still render.
        if "explanation" in alert_cols:
            rows = conn.exec_driver_sql(
                "SELECT id, explanation, risk_level FROM alert WHERE ai_explanation IS NULL"
            ).fetchall()
            for row_id, explanation, risk_level in rows:
                if explanation is None:
                    continue
                import json as _json
                fallback_explanation = _json.dumps({
                    "what_happened": explanation,
                    "why_it_matters": "",
                    "recommended_action": "Review the activity in the dashboard.",
                    "severity_label": "high" if risk_level == "high" else "medium",
                })
                conn.exec_driver_sql(
                    "UPDATE alert SET ai_explanation = ? WHERE id = ?",
                    (fallback_explanation, row_id),
                )

        # --- children table ---
        child_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(children)")}
        if "parent_id" not in child_cols:
            conn.exec_driver_sql("ALTER TABLE children ADD COLUMN parent_id INTEGER")
        if "pairing_code" not in child_cols:
            conn.exec_driver_sql("ALTER TABLE children ADD COLUMN pairing_code VARCHAR")
        if "weight_multiplier" not in child_cols:
            conn.exec_driver_sql("ALTER TABLE children ADD COLUMN weight_multiplier FLOAT DEFAULT 1.0")

        conn.commit()

# helper to get a db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
