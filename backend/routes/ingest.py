# Endpoint used by browser extension to send data to backend.
# We classify every incoming event, but we only WRITE a row to the
# database for events that are actually risk-relevant. Routine "safe"
# browsing (every page visit, every search, every metadata ping) is
# classified in-memory and then discarded instead of being persisted —
# otherwise the events table fills up with thousands of rows of normal
# activity for every few minutes of browsing.

from typing import Optional, List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Event
from services.safe_browsing import check_url_safety
from core.correlation_engine import check_for_pattern
from models.keyword_rules import check_keywords
from models.predict import predict_risk

router = APIRouter()

# default child-id
DEFAULT_CHILD_ID = "child_001"

# Event types that are pure bookkeeping/context and never carry a risk
# classification of their own (e.g. page_metadata just records a title).
# These are never worth a row on their own.
NON_ACTIONABLE_EVENT_TYPES = {"page_metadata"}

# schemas
class URLIngest(BaseModel):
    child_id: str
    url:str

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

@router.post("/ingest-url")
def ingest_url(
    payload: URLIngest,
    db: Session = Depends(get_db)
):
    """
    Extension calls this whenever the child visits a new page.
    We check the URL against Google Safe Browsing. Only flagged (unsafe)
    URLs get written to the database — a "safe" result is not logged, so
    normal browsing doesn't pile up in the events table.
    """
    is_safe = check_url_safety(payload.url)
    risk_label = "safe" if is_safe else "scam"

    if risk_label == "safe":
        return {
            "status": "checked, not saved (safe)",
            "event_id": None,
            "type": "url",
            "is_safe": is_safe,
            "risk_label": risk_label,
            "alert_triggred": False,
            "alert": None
        }

    new_event = Event(
        child_id = payload.child_id,
        type = "url",
        content = payload.url,
        risk_label = risk_label,
        risk_confidence = None # Safe Browsing gives yes/no, not a confidence score
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    alert = check_for_pattern(payload.child_id, db)

    return {
        "status":"saved!",
        "event_id":new_event.id,
        "type":"url",
        "is_safe": is_safe,
        "risk_label": risk_label,
        "alert_triggred":alert is not None,
        "alert":alert
    }

@router.post("/ingest-text")
def ingest_text(
    payload: TextIngest,
    db: Session = Depends(get_db)
):

    keyword_result = check_keywords(payload.text)

    if keyword_result:
        # Exact known red-flag phrase found -> treat as a high-confidence
        # override and skip the ML classifier entirely.
        risk_label = keyword_result["label"]
        risk_confidence = None
    else:
        # No keyword match -> fall back to the ML classifier's judgment.
        ml_result = predict_risk(payload.text)
        risk_label = ml_result["label"]
        risk_confidence = ml_result["confidence"]

    if risk_label == "safe":
        # Nothing concerning -> classify and move on, don't log it.
        return {
            "status":"checked, not saved (safe)",
            "event_id":None,
            "type":"text",
            "risk_label":risk_label,
            "alert_triggred":False,
            "alert":None
        }

    new_event = Event(
        child_id = payload.child_id,
        type = "text",
        content = payload.text,
        risk_label = risk_label,
        risk_confidence = risk_confidence
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    alert = check_for_pattern(payload.child_id, db)

    return {
        "status":"saved!",
        "event_id":new_event.id,
        "type":"text",
        "risk_label":risk_label,
        "alert_triggred":alert is not None,
        "alert": alert
    }

@router.post("/api/events")
def ingest_events(
    payload: EventBatch,
    db: Session = Depends(get_db)
):
    # endpoint for browser extension
    child_id = payload.child_id or DEFAULT_CHILD_ID
    saved_ids = []
    skipped_count = 0

    for event in payload.events:
        data: dict[str, Any] = event.data or {}
        risk_label = "safe"
        content = ""

        if event.eventType in ("page_visit","file_download"):
            """
            urlMode defaults to "domain" in the extension for privacy,so a full URL may not be present. We only call Safe Browsing when we actually have one; otherwise we just log the domain.
            """
            url = data.get("url") or data.get("sourceUrl") or ""
            content = url or data.get("domain","")
            if url:
                is_safe = check_url_safety(url)
                risk_label = "safe" if is_safe else "scam"

        elif event.eventType in ("search","form_submission"):
            content = data.get("query") or data.get("text") or data.get("value") or str(data)
            keyword_result = check_keywords(content)
            risk_label = keyword_result["label"] if keyword_result else "safe"

        elif event.eventType in NON_ACTIONABLE_EVENT_TYPES:
            # page_metadata etc. — nothing to classify, nothing to save.
            skipped_count += 1
            continue

        else:
            # file_upload and any other type we don't have a classifier
            # for yet — we don't have a way to judge risk on these, so
            # they stay "safe" and get skipped below like everything else.
            # (If you want uploads logged unconditionally regardless of
            # risk, that's a deliberate product decision — say so and
            # we'll special-case event.eventType == "file_upload" here.)
            content = str(data)

        if risk_label == "safe":
            # Routine, non-concerning activity — classified but not stored.
            skipped_count += 1
            continue

        new_event = Event(
            child_id = child_id,
            type = event.eventType,
            content = content,
            risk_label = risk_label,
            risk_confidence = None
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        saved_ids.append(new_event.id)

    alert = check_for_pattern(child_id, db)

    return {
        "status":"saved!",
        "child_id":child_id,
        "received":len(payload.events),
        "saved":len(saved_ids),
        "skipped_safe":skipped_count,
        "event_ids":saved_ids,
        "alert_triggred":alert is not None,
        "alert":alert
    }
