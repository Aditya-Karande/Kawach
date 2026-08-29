# Endpoint used by browser extension to send data to backend.
# We classify every incoming event, but we only WRITE a row to the
# database for events that are actually risk-relevant. Routine "safe"
# browsing (every page visit, every search, every metadata ping) is
# classified in-memory and then discarded instead of being persisted —
# otherwise the events table fills up with thousands of rows of normal
# activity for every few minutes of browsing.
#
# /api/signals is the one true endpoint going forward (spec Section 4.1).
# /ingest-url, /ingest-text, and /api/events are kept around for
# backward compatibility during migration.

from typing import Optional, List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Event, Child
from services.safe_browsing import check_url_safety
from core.correlation_engine import check_for_pattern
from models.keyword_rules import check_keywords, check_url_risk
from models.predict import predict_risk

router = APIRouter()

# default child-id
DEFAULT_CHILD_ID = "child_001"
DEFAULT_SESSION_ID = "default_session"

# Event types that are pure bookkeeping/context and never carry a risk
# classification of their own (e.g. page_metadata just records a title).
# These are never worth a row on their own.
NON_ACTIONABLE_EVENT_TYPES = {"page_metadata"}

VALID_SIGNAL_TYPES = {"search_query", "url_visit", "page_text", "chat_text"}

# Below this, the ML classifier's own confidence is too close to chance
# (0.25 baseline across 4 classes: safe/scam/concealment/grooming) to act
# on. Keyword matches (models/keyword_rules.py) are exact-phrase and
# always high-precision, so this threshold ONLY applies to the ML
# fallback path — see _classify_signal below. Tuned against real
# examples: genuinely risky phrasing the keyword list misses (e.g. "this
# can be our little secret ok", "whats ur snap so we can talk more
# privately") scores 0.57-0.72; benign chatter the model over-flags
# (e.g. "hii saw ur comment on that game clip, you're really good at
# this") scores 0.31-0.52. 0.55 sits in the gap between them.
ML_CONFIDENCE_THRESHOLD = 0.55


# ---------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------

class URLIngest(BaseModel):
    child_id: str
    url: str


class TextIngest(BaseModel):
    child_id: str
    text: str


class ExtensionEvent(BaseModel):
    eventId: str
    eventType: str
    timestamp: str
    data: dict = {}


class EventBatch(BaseModel):
    child_id: Optional[str] = None
    events: List[ExtensionEvent]


class SignalIngest(BaseModel):
    """Spec Section 4.1's exact payload shape for POST /api/signals."""
    child_id: str
    session_id: str
    signal_type: str  # search_query | url_visit | page_text | chat_text
    content: str
    url: Optional[str] = None
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _is_monitoring_on(child_id: str, db: Session) -> bool:
    child = db.query(Child).filter(Child.child_id == child_id).first()
    # No Child row yet -> default to monitoring ON (matches existing
    # /monitoring-status behavior for an unknown child_id).
    if child is None:
        return True
    return child.monitoring_status == "on"


def _get_multiplier(child_id: str, db: Session) -> float:
    child = db.query(Child).filter(Child.child_id == child_id).first()
    if child is None or child.weight_multiplier is None:
        return 1.0
    return child.weight_multiplier


def _classify_signal(signal_type: str, content: str, child_multiplier: float) -> dict:
    """
    Shared classification logic for a single piece of text content.
    Checks keywords first (chat_text checks personal-info/platform-switch
    first per spec), falls back to the ML classifier, and returns a
    {"label", "confidence", "weight"} dict with the weight already scaled
    by this child's feedback-loop multiplier (Section 7.1).
    """
    keyword_result = check_keywords(content, signal_type=signal_type)

    if keyword_result:
        label = keyword_result["label"]
        confidence = None
        base_weight = keyword_result["weight"]
    else:
        try:
            ml_result = predict_risk(content, signal_type=signal_type)
            label = ml_result["label"]
            confidence = ml_result["confidence"]
            base_weight = ml_result["weight"]
            # A low-confidence ML guess isn't solid enough evidence to
            # score or store on its own — this is what was letting
            # borderline compliments/small talk get flagged as
            # "grooming" at ~35-50% confidence, barely above random.
            # Downgrade to safe rather than acting on a coin-flip label.
            if label != "safe" and confidence < ML_CONFIDENCE_THRESHOLD:
                label, base_weight = "safe", 0
        except Exception as e:
            # Model file missing/corrupt, or any other classifier failure —
            # fail open to "safe" rather than 500ing the whole ingest
            # request. Keyword rules already caught the highest-confidence
            # cases above; losing the ML fallback for one event shouldn't
            # take down monitoring entirely.
            print(f"WARNING: predict_risk failed ({e}), treating as safe")
            label, confidence, base_weight = "safe", 0.0, 0

    weight = round(base_weight * child_multiplier)

    return {"label": label, "confidence": confidence, "weight": weight}


def _save_and_correlate(
    db: Session,
    child_id: str,
    session_id: Optional[str],
    signal_type: str,
    content: str,
    risk_label: str,
    risk_confidence,
    weight: int,
):
    new_event = Event(
        child_id=child_id,
        session_id=session_id,
        signal_type=signal_type,
        content=content,
        risk_label=risk_label,
        risk_confidence=risk_confidence,
        weight=weight,
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    outcome = check_for_pattern(child_id, session_id, db)

    # Tier 3 -> fire the alert email. Import kept local to avoid a
    # circular import (services/email.py doesn't need to be loaded for
    # every ingest, only when there's actually something to send).
    if outcome and outcome.get("tier") == 3 and outcome.get("alert_id"):
        try:
            from services.email import send_tier3_alert_email
            send_tier3_alert_email(child_id, outcome, db)
        except Exception as e:
            print(f"WARNING: failed to send tier-3 alert email: {e}")

    return new_event, outcome


# ---------------------------------------------------------------------
# POST /api/signals — the one true endpoint (spec Section 4.1)
# ---------------------------------------------------------------------

@router.post("/api/signals")
def ingest_signal(
    payload: SignalIngest,
    db: Session = Depends(get_db),
):
    if not _is_monitoring_on(payload.child_id, db):
        return {"status": "monitoring off, not processed", "blocked": False}

    signal_type = payload.signal_type
    if signal_type not in VALID_SIGNAL_TYPES:
        return {"status": "error", "detail": f"invalid signal_type: {signal_type!r}"}

    # url_visit: check Safe Browsing first. A confirmed match blocks
    # instantly with no LLM call and bypasses the weighted scoring
    # entirely, same as before.
    if signal_type == "url_visit":
        url = payload.url or payload.content
        is_safe = check_url_safety(url)

        if not is_safe:
            new_event = Event(
                child_id=payload.child_id,
                session_id=payload.session_id,
                signal_type="url_visit",
                content=url,
                risk_label="confirmed_scam",
                risk_confidence=None,
                weight=0,  # confirmed matches bypass the weighted-score path entirely
            )
            db.add(new_event)
            db.commit()
            db.refresh(new_event)
            return {
                "status": "blocked",
                "blocked": True,
                "event_id": new_event.id,
                "risk_label": "confirmed_scam",
            }

        # Not a confirmed match — check it against the URL-risk heuristic
        # (models/keyword_rules.py:check_url_risk) rather than treating
        # every not-yet-confirmed URL as risky. Most browsing is neither
        # confirmed-malicious nor scam-shaped, and should score 0/not be
        # saved at all, same as any other "safe" signal.
        multiplier = _get_multiplier(payload.child_id, db)
        url_risk = check_url_risk(url)

        if url_risk is None:
            return {"status": "checked, not saved (safe)", "blocked": False, "event_id": None}

        weight = round(url_risk["weight"] * multiplier)

        if weight == 0:
            return {"status": "checked, not saved (safe)", "blocked": False, "event_id": None}

        new_event, outcome = _save_and_correlate(
            db, payload.child_id, payload.session_id, "url_visit", url,
            "unconfirmed", None, weight,
        )
        return {
            "status": "saved",
            "blocked": False,
            "event_id": new_event.id,
            "risk_label": "unconfirmed",
            "outcome": outcome,
        }

    # search_query / page_text / chat_text: classify via keywords -> ML.
    multiplier = _get_multiplier(payload.child_id, db)
    classification = _classify_signal(signal_type, payload.content, multiplier)

    if classification["label"] == "safe" or classification["weight"] == 0:
        return {"status": "checked, not saved (safe)", "blocked": False, "event_id": None}

    new_event, outcome = _save_and_correlate(
        db, payload.child_id, payload.session_id, signal_type, payload.content,
        classification["label"], classification["confidence"], classification["weight"],
    )

    return {
        "status": "saved",
        "blocked": False,
        "event_id": new_event.id,
        "risk_label": classification["label"],
        "outcome": outcome,
    }


# ---------------------------------------------------------------------
# GET /api/monitoring/status/{child_id} — spec's path-param form.
# routes/monitoring.py owns the query-param legacy version; this alias
# lives here since it's part of the signal-ingest contract the extension
# checks before sending anything.
# ---------------------------------------------------------------------

@router.get("/api/monitoring/status/{child_id}")
def monitoring_status_path(child_id: str, db: Session = Depends(get_db)):
    child = db.query(Child).filter(Child.child_id == child_id).first()
    if child is None:
        return {"child_id": child_id, "monitoring_status": "on"}
    return {"child_id": child.child_id, "monitoring_status": child.monitoring_status}


# ---------------------------------------------------------------------
# Legacy endpoints — kept for backward compatibility during migration.
# ---------------------------------------------------------------------

@router.post("/ingest-url")
def ingest_url(
    payload: URLIngest,
    db: Session = Depends(get_db)
):
    """
    Legacy endpoint. Extension should migrate to POST /api/signals with
    signal_type="url_visit". Kept working via the same Safe Browsing
    instant-block path; anything that isn't a confirmed match is scored
    as "unconfirmed" like the new endpoint, but with no session_id.
    """
    is_safe = check_url_safety(payload.url)

    if not is_safe:
        new_event = Event(
            child_id=payload.child_id,
            session_id=None,
            signal_type="url_visit",
            content=payload.url,
            risk_label="confirmed_scam",
            risk_confidence=None,
            weight=0,
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {
            "status": "saved!",
            "event_id": new_event.id,
            "type": "url",
            "is_safe": is_safe,
            "risk_label": "confirmed_scam",
            "alert_triggred": False,
            "alert": None,
        }

    multiplier = _get_multiplier(payload.child_id, db)
    url_risk = check_url_risk(payload.url)

    if url_risk is None:
        return {
            "status": "checked, not saved (safe)",
            "event_id": None,
            "type": "url",
            "is_safe": is_safe,
            "risk_label": "safe",
            "alert_triggred": False,
            "alert": None
        }

    weight = round(url_risk["weight"] * multiplier)

    if weight == 0:
        return {
            "status": "checked, not saved (safe)",
            "event_id": None,
            "type": "url",
            "is_safe": is_safe,
            "risk_label": "safe",
            "alert_triggred": False,
            "alert": None
        }

    new_event, outcome = _save_and_correlate(
        db, payload.child_id, None, "url_visit", payload.url, "unconfirmed", None, weight,
    )

    return {
        "status": "saved!",
        "event_id": new_event.id,
        "type": "url",
        "is_safe": is_safe,
        "risk_label": "unconfirmed",
        "alert_triggred": outcome is not None and outcome.get("alert_id") is not None,
        "alert": outcome
    }

@router.post("/ingest-text")
def ingest_text(
    payload: TextIngest,
    db: Session = Depends(get_db)
):
    """Legacy endpoint. Extension should migrate to POST /api/signals."""
    multiplier = _get_multiplier(payload.child_id, db)
    classification = _classify_signal("page_text", payload.text, multiplier)

    if classification["label"] == "safe" or classification["weight"] == 0:
        return {
            "status": "checked, not saved (safe)",
            "event_id": None,
            "type": "text",
            "risk_label": "safe",
            "alert_triggred": False,
            "alert": None
        }

    new_event, outcome = _save_and_correlate(
        db, payload.child_id, None, "page_text", payload.text,
        classification["label"], classification["confidence"], classification["weight"],
    )

    return {
        "status": "saved!",
        "event_id": new_event.id,
        "type": "text",
        "risk_label": classification["label"],
        "alert_triggred": outcome is not None and outcome.get("alert_id") is not None,
        "alert": outcome
    }

@router.post("/api/events")
def ingest_events(
    payload: EventBatch,
    db: Session = Depends(get_db)
):
    """Legacy batch endpoint used by the current extension build."""
    child_id = payload.child_id or DEFAULT_CHILD_ID
    multiplier = _get_multiplier(child_id, db)
    saved_ids = []
    skipped_count = 0

    for event in payload.events:
        data: dict[str, Any] = event.data or {}
        risk_label = "safe"
        confidence = None
        weight = 0
        content = ""
        signal_type = "page_text"

        if event.eventType in ("page_visit", "file_download"):
            """
            urlMode defaults to "domain" in the extension for privacy,so a full URL may not be present.
            We only call Safe Browsing when we actually have one; otherwise we just log the domain.
            """
            signal_type = "url_visit"
            url = data.get("url") or data.get("sourceUrl") or ""
            content = url or data.get("domain", "")
            if url:
                is_safe = check_url_safety(url)
                if not is_safe:
                    risk_label = "confirmed_scam"
                    weight = 0
                else:
                    url_risk = check_url_risk(url)
                    if url_risk is not None:
                        risk_label = "unconfirmed"
                        weight = round(url_risk["weight"] * multiplier)
                    # else: ordinary browsing, stays risk_label="safe"/weight=0
                    # and gets skipped below like any other safe signal.

        elif event.eventType == "search":
            signal_type = "search_query"
            content = data.get("query") or data.get("text") or data.get("value") or str(data)
            classification = _classify_signal(signal_type, content, multiplier)
            risk_label, confidence, weight = classification["label"], classification["confidence"], classification["weight"]

        elif event.eventType == "chat_message":
            signal_type = "chat_text"
            content = data.get("text") or data.get("value") or str(data)
            classification = _classify_signal(signal_type, content, multiplier)
            risk_label, confidence, weight = classification["label"], classification["confidence"], classification["weight"]

        elif event.eventType == "form_submission":
            signal_type = "page_text"
            content = data.get("text") or data.get("value") or str(data)
            classification = _classify_signal(signal_type, content, multiplier)
            risk_label, confidence, weight = classification["label"], classification["confidence"], classification["weight"]

        elif event.eventType in NON_ACTIONABLE_EVENT_TYPES:
            # page_metadata etc. — nothing to classify, nothing to save.
            skipped_count += 1
            continue

        else:
            # file_upload and any other type we don't have a classifier
            # for yet — we don't have a way to judge risk on these, so
            # they stay "safe" and get skipped below like everything else.
            content = str(data)

        if risk_label == "safe" or (risk_label != "confirmed_scam" and weight == 0):
            # Routine, non-concerning activity — classified but not stored.
            skipped_count += 1
            continue

        new_event = Event(
            child_id=child_id,
            session_id=None,
            signal_type=signal_type,
            content=content,
            risk_label=risk_label,
            risk_confidence=confidence,
            weight=weight,
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        saved_ids.append(new_event.id)

    outcome = check_for_pattern(child_id, None, db)

    return {
        "status": "saved!",
        "child_id": child_id,
        "received": len(payload.events),
        "saved": len(saved_ids),
        "skipped_safe": skipped_count,
        "event_ids": saved_ids,
        "alert_triggred": outcome is not None and outcome.get("alert_id") is not None,
        "alert": outcome
    }
