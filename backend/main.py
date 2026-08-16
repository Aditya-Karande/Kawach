from fastapi import FastAPI
from database import init_db

from routes import ingest, monitoring

app = FastAPI(title="Kawach")

init_db()

# plugin endpoints
app.include_router(ingest.router)
app.include_router(monitoring.router)

@app.get("/health")
def health():
    return {"status":"ok"}