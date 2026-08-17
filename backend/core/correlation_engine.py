from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from database import Event, Alert

# Short term window setting
SHORT_WINDOW_MINUTES = 20
SHORT_TERM_THRESHOLD = 2

# Long term window setting
LONG_WINDOW_DAYS = 7
LONG_TERM_THRESHOLD = 3

# Don't create a new LONG-TERM alert for the same child more than once
# within this cooldown period, even if the pattern still holds — otherwise
# every single new event would re-trigger a duplicate alert.
LONG_TERM_ALERT_COOLDOWN_HOURS = 24

def check_for_pattern(
        child_id: str,
        db: Session
) -> dict | None:
    """
    Runs BOTH the short-term and long-term checks for this child.
    Returns the short-term alert if one was created (since that's the
    more time-sensitive/urgent one to surface immediately), otherwise
    returns the long-term alert if one was created, otherwise None.
    """
    short_term_alert = _check_window(
        child_id=child_id,
        db=db,
        window=timedelta(minutes=SHORT_WINDOW_MINUTES),
        threshold=SHORT_TERM_THRESHOLD,
        pattern_type="short_term"
    )

    long_term_alert = _check_long_term(child_id=child_id, db=db)

    return short_term_alert or long_term_alert

def _check_window(
        child_id: str,
        db: Session,
        window: timedelta,
        threshold: int,
        pattern_type: str,
) -> dict | None:
    """
    Shared logic: look at events for this child within `window`,
    and if `threshold` or more are risky, create a combined alert.
    """
    cutoff_time = datetime.now(timezone.utc) - window

    recent_events = (
        db.query(Event)
        .filter(Event.child_id == child_id)
        .filter(Event.timestamp >= cutoff_time)
        .order_by(Event.timestamp.desc())
        .all()
    )

    risky_events = [e for e in recent_events if e.risk_label and e.risk_label != "safe"]

    if len(risky_events) < threshold:
        return None

    explanation = build_simple_explanation(risky_events,pattern_type,window)
    risk_level = "high" if len(risky_events) >= threshold + 2 else "medium"

    new_alert = Alert(
        child_id = child_id,
        explanation = explanation,
        risk_level = risk_level
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    return{
        "alert_id":new_alert.id,
        "child_id":child_id,
        "risk_level":risk_level,
        "explanation":explanation,
        "triggred_by_event_count":len(risky_events),
        "pattern_type":pattern_type
    }

def _check_long_term(
        child_id: str,
        db: Session,
) -> dict | None:
    """
    Long-term check, with a cooldown so we don't spam duplicate alerts
    for the same slow-building pattern every time a new event comes in.
    """
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(hours=LONG_TERM_ALERT_COOLDOWN_HOURS)

    recent_long_term_alert = (
        db.query(Alert)
        .filter(Alert.child_id == child_id)
        .filter(Alert.explanation.like("%long-term%"))
        .filter(Alert.timestamp >= cooldown_cutoff)
        .first()
    )

    if recent_long_term_alert is not None:
        # We already alerted the parent about this slow-building pattern recently — don't create a duplicate.
        return None

    return _check_window(
        child_id=child_id,
        db=db,
        window=timedelta(days=LONG_WINDOW_DAYS),
        threshold=LONG_TERM_THRESHOLD,
        pattern_type="long_term"
    )

def build_simple_explanation(
        risky_events: list[Event],
        pattern_type: str,
        window:timedelta
) -> str:
    """
    Builds a plain-English summary of what was flagged, without any LLM.
    """
    label_counts: dict[str,int] = {}
    for event in risky_events:
        label_counts[event.risk_label] = label_counts.get(event.risk_label,0) + 1

    parts = []
    for label,count in label_counts.items():
        noun = "event" if count == 1 else "events"
        parts.append(f"{count} '{label}' {noun}")

    summary = ", ".join(parts)

    if pattern_type == "long_term":
        timeframe_desc = f"spread across the last {window.days} days (long-term pattern)"
    else:
        minutes = int(window.total_seconds() // 60)
        timeframe_desc = f"within the last {minutes} minutes." 

    return f"{len(risky_events)} concerning signals detected: {summary}, {timeframe_desc}."