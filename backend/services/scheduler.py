"""
services/scheduler.py
======================
In-process weekly digest scheduling via APScheduler, per spec Section
7.4. Started from main.py on app startup. Runs every Monday 08:00
server time by default — override with DIGEST_DAY_OF_WEEK / DIGEST_HOUR
in .env if needed.
"""

import os
from apscheduler.schedulers.background import BackgroundScheduler

from services.email import run_weekly_digest_for_all_children

DIGEST_DAY_OF_WEEK = os.getenv("DIGEST_DAY_OF_WEEK", "mon")
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "8"))

_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_weekly_digest_for_all_children,
        trigger="cron",
        day_of_week=DIGEST_DAY_OF_WEEK,
        hour=DIGEST_HOUR,
        id="weekly_digest",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler
