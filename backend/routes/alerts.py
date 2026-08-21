from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Alert, Event, Child, Feedback, Parent
from core.security import get_current_parent

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Bounds for the per-child weight multiplier the feedback loop adjusts.
# Never fully zeroes out future scoring (floor), and never runs away
# unbounded (ceiling). "not_a_concern" verdicts step the multiplier down
# toward the floor (system gets less trigger-happy for this child).
# "reviewed" (confirmed real) verdicts step it up toward the ceiling, so
# a child with a track record of real concerns gets scored as higher-risk
# going forward, not just walked back to the 1.0 baseline.
MULTIPLIER_FLOOR = 0.4
MULTIPLIER_CEILING = 1.5
MULTIPLIER_STEP_DOWN = 0.9   # applied on "not_a_concern"
MULTIPLIER_STEP_UP = 1.05    # applied on "reviewed" (confirmed real)


class FeedbackRequest(BaseModel):
    parent_verdict: str  # "reviewed" | "not_a_concern"


def _get_owned_child(child_id: str, current_parent: Parent, db: Session) -> Child:
    child = db.query(Child).filter(Child.child_id == child_id).first()
    if child is None or child.parent_id != current_parent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    return child


@router.get("/{child_id}")
def get_alerts(
    child_id: str,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """
    Returns the alert feed for a child, most recent first, each with its
    score breakdown — reads contributing_signal_ids back out and joins
    to the events table (spec Section 7.2's expandable breakdown).
    """
    _get_owned_child(child_id, current_parent, db)  # 404s if not owned

    alerts = (
        db.query(Alert)
        .filter(Alert.child_id == child_id)
        .order_by(Alert.timestamp.desc())
        .all()
    )

    result = []
    for alert in alerts:
        signal_ids = alert.contributing_signal_ids or []
        contributing_events = (
            db.query(Event).filter(Event.id.in_(signal_ids)).all() if signal_ids else []
        )
        result.append({
            "id": alert.id,
            "child_id": alert.child_id,
            "tier": alert.tier,
            "score": alert.score,
            "status": alert.status,
            "ai_explanation": alert.ai_explanation,
            "timestamp": alert.timestamp,
            "updated_at": alert.updated_at,
            "score_breakdown": [
                {
                    "event_id": e.id,
                    "signal_type": e.signal_type,
                    "risk_label": e.risk_label,
                    "weight": e.weight,
                    "content": e.content,
                    "timestamp": e.timestamp,
                }
                for e in contributing_events
            ],
        })

    return result


@router.post("/{alert_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    alert_id: int,
    payload: FeedbackRequest,
    current_parent: Parent = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    if payload.parent_verdict not in ("reviewed", "not_a_concern"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid parent_verdict")

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    _get_owned_child(alert.child_id, current_parent, db)  # 404s if not owned

    feedback = Feedback(alert_id=alert_id, parent_verdict=payload.parent_verdict)
    db.add(feedback)

    alert.status = "reviewed" if payload.parent_verdict == "reviewed" else "dismissed"

    # Bump the child's per-signal weight multiplier (Section 7.1). A
    # string of "not_a_concern" verdicts gradually raises the bar for
    # future alerts on this child; a "reviewed" (confirmed real) verdict
    # raises the multiplier toward MULTIPLIER_CEILING, so repeated
    # confirmed concerns make future scoring more sensitive for this
    # child instead of just resetting to the 1.0 baseline.
    child = db.query(Child).filter(Child.child_id == alert.child_id).first()
    if child is not None:
        current = child.weight_multiplier or 1.0
        if payload.parent_verdict == "not_a_concern":
            child.weight_multiplier = max(MULTIPLIER_FLOOR, round(current * MULTIPLIER_STEP_DOWN, 3))
        else:
            child.weight_multiplier = min(MULTIPLIER_CEILING, round(current * MULTIPLIER_STEP_UP, 3))

    db.commit()

    return {
        "alert_id": alert_id,
        "parent_verdict": payload.parent_verdict,
        "child_weight_multiplier": child.weight_multiplier if child else None,
    }
