from fastapi import FastAPI

app = FastAPI(title="Zorum AI")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}