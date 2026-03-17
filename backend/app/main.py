"""
HireRight Backend - FastAPI Application

Main entry point for the HireRight API with LangGraph multi-agent system.
"""

import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, cover_letter, debate, headhunter, health, jobs, match, profile
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    setup_logging()

    # ── Credential Validation Banner ──
    print("\n" + "=" * 60)
    print("🚀 HireRight Backend Starting Up")
    print("=" * 60)
    print(f"  GOOGLE_API_KEY  Loaded: {bool(os.getenv('GOOGLE_API_KEY'))}")
    print(f"  SUPABASE_URL    Loaded: {bool(os.getenv('SUPABASE_URL'))}")
    print(f"  SUPABASE_KEY    Loaded: {bool(os.getenv('SUPABASE_KEY'))}")
    print(f"  GITHUB_TOKEN    Loaded: {bool(os.getenv('GITHUB_TOKEN'))}")
    print(f"  TAVILY_API_KEY  Loaded: {bool(os.getenv('TAVILY_API_KEY'))}")
    print(f"  CORS Origins:   {settings.cors_origins}")
    print(f"  Gemini Model:   {settings.gemini_model}")
    print(f"  Embedding Dim:  {settings.embedding_dimension}")
    print("=" * 60)

    # Validate critical credentials
    missing = []
    if not os.getenv('GOOGLE_API_KEY'):
        missing.append('GOOGLE_API_KEY')
    if not os.getenv('SUPABASE_URL'):
        missing.append('SUPABASE_URL')
    if not os.getenv('SUPABASE_KEY'):
        missing.append('SUPABASE_KEY')
    if missing:
        print(f"  ⚠️  WARNING: Missing critical env vars: {', '.join(missing)}")
        print(f"  ⚠️  The /match endpoint WILL FAIL without these!")
    else:
        print("  ✅ All critical credentials loaded successfully.")
    print("=" * 60 + "\n")

    yield
    # Shutdown
    print("\n🛑 HireRight Backend shutting down...")


# Create FastAPI application
app = FastAPI(
    title="HireRight API",
    description="AI-powered job matching with multi-agent debates",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS — ensure localhost:8501 (Streamlit) is always allowed
cors_origins = list(set(settings.cors_origins + [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
]))
print(f"DEBUG: CORS origins configured → {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(profile.router, prefix="/api/v1", tags=["Profile"])
app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
app.include_router(match.router, prefix="/api/v1", tags=["Match"])
app.include_router(cover_letter.router, prefix="/api/v1", tags=["Cover Letter"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(headhunter.router, prefix="/api/v1", tags=["Headhunter"])
app.include_router(debate.router, prefix="/api/v1/debate", tags=["Agent Debate"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "HireRight API",
        "version": "0.1.0",
        "docs": "/docs",
    }
