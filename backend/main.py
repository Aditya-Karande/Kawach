from fastapi import FastAPI
from database import init_db

from routes import ingest

app = FastAPI(title="Kawach")

init_db()

# plugin ingest endpoint
app.include_router(ingest.router)

@app.get("/health")
def health():
    return {"status":"ok"}