from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth.router import router as auth_router

app = FastAPI(title="Zorum AI")

# Browsers block cross-origin JS calls unless the API allows the origin.
# Dev: Next.js runs on :3000, API on :8000 — different origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
