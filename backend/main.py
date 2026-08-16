from fastapi import FastAPI 

app = FastAPI(title="Kawach")

@app.get("/health")
def health():
    return {"status":"ok"}