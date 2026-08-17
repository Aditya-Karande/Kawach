# Endpoint used by browser extension to send data to backend.
# for now it just saving whatever it got in "events" table..
# no LLM, AI yet.. (future phase.)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, Event
from services.safe_browsing import check_url_safety
from core.correlation_engine import check_for_pattern
from models.keyword_rules import check_keywords

router = APIRouter()

# schemas
class URLIngest(BaseModel):
    child_id: str
    url:str

class TextIngest(BaseModel):
    child_id: str
    text: str

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
    risk_label = keyword_result["label"] if keyword_result else "safe"

    new_event = Event(
        child_id = payload.child_id,
        type = "text",
        content = payload.text,
        risk_label = None,
        risk_confidence = None
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