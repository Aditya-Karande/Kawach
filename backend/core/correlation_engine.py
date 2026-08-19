from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from database import Event, Alert
from services.llm_report import analyze_and_explain
from core.scoring import tier_for_score

# Rolling window the score is summed over, scoped by session_id per spec
# Section 5 (not just child_id — a new session starts a fresh score).
WINDOW_MINUTES = 30


def check_for_pattern(
        child_id: str,
        session_id: str | None,
        db: Session,
) -> dict | None:
    """
    Sums Event.weight over the rolling window for this child+session and
    routes the total into a tier:

      tier None (score 0)   -> nothing to do
      tier 1  (score 1-2)   -> already logged as a normal Event row, no
                                further action, no one is told
      tier 2  (score 3-5)   -> in-browser nudge shown to the child; still
                                just logged, no Alert row, no LLM call
      tier 3  (score 6+)    -> LLM explanation generated, Alert row
                                created/updated, parent gets pushed a
                                notification (handled by the caller in
                                routes/ingest.py + services/email.py)

    A confirmed Safe Browsing match bypasses this function entirely and
    blocks instantly — that happens upstream in ingest.py and never
    reaches here.

    Returns a dict describing the outcome (for the API response) or None
    if nothing scored above 0 in the window.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)

    query = (
        db.query(Event)
        .filter(Event.child_id == child_id)
        .filter(Event.timestamp >= cutoff_time)
    )
    if session_id:
        query = query.filter(Event.session_id == session_id)

    recent_events = query.order_by(Event.timestamp.desc()).all()
    scored_events = [e for e in recent_events if e.weight]

    score = sum(e.weight for e in scored_events)
    tier = tier_for_score(score)

    if tier is None:
        return None

    if tier in (1, 2):
        # Tier 1: log silently, nobody is told.
        # Tier 2: in-browser nudge shown to the child, logged — but per
        # spec this is NOT sent to the parent, so no Alert row is created,
        # and there's no LLM call either. The events are already
        # persisted by the caller before check_for_pattern runs, so
        # there's nothing further to write here.
        return {
            "tier": tier,
            "score": score,
            "child_id": child_id,
            "session_id": session_id,
            "nudge": tier == 2,
            "alert_id": None,
            "ai_explanation": None,
        }

    # --- tier 3: the only tier that calls the LLM and creates an Alert ---

    existing_alert = (
        db.query(Alert)
        .filter(Alert.child_id == child_id)
        .filter(Alert.status == "new")
        .filter(Alert.updated_at >= cutoff_time)
        .order_by(Alert.updated_at.desc())
        .first()
    )

    contributing_ids = [e.id for e in scored_events]

    # No new contributing events since the existing open alert was last
    # updated -> nothing has changed, don't bother re-calling the LLM.
    if existing_alert is not None and set(existing_alert.contributing_signal_ids or []) == set(contributing_ids):
        return None

    llm_result = analyze_and_explain(scored_events)

    if not llm_result["is_genuine_concern"]:
        # LLM judged this as a false positive (e.g. words matched but
        # context was harmless) — don't create/update an alert, don't
        # bother the parent.
        print(f"LLM judged this cluster as a false positive for child {child_id}, no alert created.")
        return None

    ai_explanation = llm_result["ai_explanation"]

    if existing_alert is not None:
        existing_alert.score = score
        existing_alert.tier = tier
        existing_alert.contributing_signal_ids = contributing_ids
        existing_alert.ai_explanation = ai_explanation
        existing_alert.event_count = len(contributing_ids)
        existing_alert.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_alert)
        alert_row = existing_alert
    else:
        alert_row = Alert(
            child_id=child_id,
            tier=tier,
            score=score,
            contributing_signal_ids=contributing_ids,
            ai_explanation=ai_explanation,
            status="new",
            event_count=len(contributing_ids),
        )
        db.add(alert_row)
        db.commit()
        db.refresh(alert_row)

    return {
        "tier": tier,
        "score": score,
        "child_id": child_id,
        "session_id": session_id,
        "nudge": False,
        "alert_id": alert_row.id,
        "ai_explanation": ai_explanation,
    }
