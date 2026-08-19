from fastapi import FastAPI
from database import init_db

from routes import ingest, monitoring, auth, alerts, guardians, children

app = FastAPI(title="Kawach")

init_db()

# plugin endpoints
app.include_router(ingest.router)
app.include_router(monitoring.router)
app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(guardians.router)
app.include_router(children.router)


@app.on_event("startup")
def _start_background_jobs():
    # Weekly digest scheduling (spec Section 7.4). Wrapped in try/except
    # so a misconfigured/missing scheduler dependency never blocks the
    # API itself from starting up.
    try:
        from services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"WARNING: could not start weekly digest scheduler: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}
