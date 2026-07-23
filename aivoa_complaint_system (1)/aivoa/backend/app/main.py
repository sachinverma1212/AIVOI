import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import complaints, extraction, chat, ai_tools

logging.basicConfig(level=logging.INFO)
settings = get_settings()

# Create tables on startup (fine for an assessment/demo; use Alembic migrations in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AIVOA Customer Complaint Management System",
    description="AI-powered complaint intake & triage for pharmaceutical QMS (API/FDF manufacturing).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(complaints.router)
app.include_router(extraction.router)
app.include_router(chat.router)
app.include_router(ai_tools.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
