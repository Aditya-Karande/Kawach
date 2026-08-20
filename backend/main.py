from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db

from routes import ingest, monitoring, auth, alerts, guardians, children

app = FastAPI(title="Kawach")

# CORS: the demo page (demo/index.html) and any future dashboard call
# this API from a different origin via plain fetch(), which the browser
# blocks by default without these headers. allow_origins=["*"] is fine
# for local development / the demo; lock this down to your actual
# dashboard's origin(s) before deploying anywhere real, since "*" plus
# credentialed requests is not something you want in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
