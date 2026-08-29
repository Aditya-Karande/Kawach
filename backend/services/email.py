"""
services/email.py
==================
Sends the instant tier-3 alert email (to the parent and any second
guardian), and the weekly digest (Section 7.4). Uses plain smtplib
against whatever SMTP relay is configured in .env — if nothing is
configured, calls are logged and skipped rather than raising, same
fail-soft pattern as services/safe_browsing.py and services/llm_report.py.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("ALERTS_FROM_EMAIL", "alerts@safesignal.app")


def _send(to_emails: list[str], subject: str, body: str) -> bool:
    if not to_emails:
        return False

    if not (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
        print(f"WARNING: SMTP not configured in .env — skipping email. "
              f"Would have sent {subject!r} to {to_emails}")
        return False

    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_emails, msg.as_string())
        return True
    except Exception as e:
        print(f"WARNING: failed to send email ({e})")
        return False


def _recipients_for_child(child_id: str, db: Session) -> list[str]:
    from database import Child, Guardian, Parent

    child = db.query(Child).filter(Child.child_id == child_id).first()
    if child is None:
        return []

    emails = []
    if child.parent_id:
        parent = db.query(Parent).filter(Parent.id == child.parent_id).first()
        if parent:
            emails.append(parent.email)

    guardians = db.query(Guardian).filter(Guardian.child_id == child.id).all()
    emails.extend(g.email for g in guardians)

    return emails


def send_tier3_alert_email(child_id: str, outcome: dict, db: Session) -> bool:
    """
    Instant email for a tier-3 (score 6+) cluster — sent to the parent
    and any second guardian configured for this child.
    """
    recipients = _recipients_for_child(child_id, db)
    explanation = outcome.get("ai_explanation") or {}

    subject = "SafeSignal: a new alert needs your attention"
    body = (
        f"What happened: {explanation.get('what_happened', '')}\n\n"
        f"Why it matters: {explanation.get('why_it_matters', '')}\n\n"
        f"Recommended action: {explanation.get('recommended_action', '')}\n\n"
        f"Open the SafeSignal dashboard to see the full details for this alert."
    )

    return _send(recipients, subject, body)


def send_weekly_digest(child_id: str, db: Session) -> bool:
    """
    Aggregate counts only (sites visited, searches monitored, alerts by
    tier) for the past 7 days — sent every week regardless of alert
    activity (spec Section 7.4).
    """
    from database import Event, Alert

    since = datetime.now(timezone.utc) - timedelta(days=7)

    events = db.query(Event).filter(Event.child_id == child_id, Event.timestamp >= since).all()
    alerts = db.query(Alert).filter(Alert.child_id == child_id, Alert.timestamp >= since).all()

    sites_visited = sum(1 for e in events if e.signal_type == "url_visit")
    searches_monitored = sum(1 for e in events if e.signal_type == "search_query")
    alerts_by_tier = {1: 0, 2: 0, 3: 0}
    for a in alerts:
        alerts_by_tier[a.tier] = alerts_by_tier.get(a.tier, 0) + 1

    recipients = _recipients_for_child(child_id, db)

    subject = "SafeSignal: your weekly digest"
    body = (
        f"Here's a quick summary of the past 7 days:\n\n"
        f"Sites visited (flagged/unconfirmed): {sites_visited}\n"
        f"Searches monitored: {searches_monitored}\n"
        f"Alerts sent to you (tier 3): {alerts_by_tier[3]}\n"
        f"Nudges shown to your child (tier 2): {alerts_by_tier[2]}\n"
        f"Low-level signals logged only (tier 1): {alerts_by_tier[1]}\n"
    )

    return _send(recipients, subject, body)


def run_weekly_digest_for_all_children():
    """
    Entry point for the scheduled job (see services/scheduler.py). Sends
    a digest for every child in the system, regardless of whether they
    had any alerts this week.
    """
    from database import SessionLocal, Child

    db = SessionLocal()
    try:
        for child in db.query(Child).all():
            send_weekly_digest(child.child_id, db)
    finally:
        db.close()
