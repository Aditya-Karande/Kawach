# Endpoint used by browser extension to send data to backend.
# for now it just saving whatever it got in "events" table..
# no LLM, AI yet.. (future phase.)

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

# schemas
class URLIngest(BaseModel):
    child_id: str
    url:str

class TextIngest(BaseModel):
    child_id: str
    text: str

class ExtensionEvent(BaseModel):
    enventID: str
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
    We check the URL against Google Safe Browsing, then save the result.
    """
    is_safe = check_url_safety(payload.url)
    risk_label = "safe" if is_safe else "scam"
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
                risk_label - "safe" if is_safe else "scam"

            elif event.eventType in ("search","from_submission"):
                content = data.get("query") or data.get("text") or data.get("value") or str(data)
                keyword_result = check_keywords(content)
                risk_label = keyword_result["label"] if keyword_result else "safe"

            else:
            # file_upload, page_metadata, etc. — log-only for now, no
            # classifier/keyword check applies to these event types.
                content = str(data)

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
            "event_ids":saved_ids,
            "alert_triggred":alert is not None,
            "alert":alert
        }