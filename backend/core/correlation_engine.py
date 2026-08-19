from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from database import Event, Alert
from services.llm_report import analyze_and_explain

# Short term window setting
SHORT_WINDOW_MINUTES = 20
SHORT_TERM_THRESHOLD = 2

# Long term window setting
LONG_WINDOW_DAYS = 7
LONG_TERM_THRESHOLD = 3

def check_for_pattern(
        child_id: str,
        db: Session
) -> dict | None:
    """
    Runs BOTH the short-term and long-term checks for this child.
    Returns the short-term alert if one was created/updated (since that's
    the more time-sensitive/urgent one to surface immediately), otherwise
    returns the long-term one, otherwise None.
    """
    short_term_alert = _check_window(
        child_id=child_id,
        db=db,
        window=timedelta(minutes=SHORT_WINDOW_MINUTES),
        threshold=SHORT_TERM_THRESHOLD,
        pattern_type="short_term"
    )

    long_term_alert = _check_window(
        child_id=child_id,
        db=db,
        window=timedelta(days=LONG_WINDOW_DAYS),
        threshold=LONG_TERM_THRESHOLD,
        pattern_type="long_term"
    )

    return short_term_alert or long_term_alert


def _check_window(
        child_id: str,
        db: Session,
        window: timedelta,
        threshold: int,
        pattern_type: str,
) -> dict | None:
    """
    Shared logic: look at events for this child within `window`, and if
    `threshold` or more are risky, produce ONE alert for that pattern.

    Key fix: if an alert for this same child + pattern_type is already
    "open" (created within the current window), we UPDATE it in place
    with a fresh explanation covering ALL the risky events currently in
    the window, instead of inserting a new row. That's what stops the
    parent dashboard from getting flooded with a new near-duplicate alert
    every time one more risky event trickles in — they get a single,
    growing explanation instead.
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

    # Is there already an open alert for this exact pattern? "Open" means
    # it was created/updated within this same window, i.e. it's still
    # describing the current situation rather than a resolved past one.
    existing_alert = (
        db.query(Alert)
        .filter(Alert.child_id == child_id)
        .filter(Alert.pattern_type == pattern_type)
        .filter(Alert.updated_at >= cutoff_time)
        .order_by(Alert.updated_at.desc())
        .first()
    )

    # No new risky events since the existing alert was last updated ->
    # nothing has changed, don't bother re-calling the LLM or bumping it.
    if existing_alert is not None and existing_alert.event_count >= len(risky_events):
        return None

    """
    Call the LLM ONLY here — at alert-time, not per-message.
    It judges genuine intent (not just keyword presence) and writes the explanation, both in one call.
    """
    LLM_result = analyze_and_explain(risky_events)

    if not LLM_result["is_genuine_concern"]:
        # LLM judged this as a false positive (e.g. words matched but context was harmless) — don't create an alert, don't bother the parent.
        print(f"LLM judged this cluster as a false positive for child {child_id}, no alert created.")
        return None

    explanation = LLM_result["explanation"]
    if pattern_type == "long_term":
        explanation += " (long-term pattern)"
    risk_level = LLM_result["risk_level"]

    if existing_alert is not None:
        existing_alert.explanation = explanation
        existing_alert.risk_level = risk_level
        existing_alert.event_count = len(risky_events)
        existing_alert.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_alert)
        alert_row = existing_alert
    else:
        alert_row = Alert(
            child_id=child_id,
            explanation=explanation,
            risk_level=risk_level,
            pattern_type=pattern_type,
            event_count=len(risky_events),
        )
        db.add(alert_row)
        db.commit()
        db.refresh(alert_row)

    return {
        "alert_id": alert_row.id,
        "child_id": child_id,
        "risk_level": risk_level,
        "explanation": explanation,
        "triggred_by_event_count": len(risky_events),
        "pattern_type": pattern_type
    }
