"""
ReelForge - Instagram Automation Tool
======================================

An agentic framework for automating Instagram Reel publishing.
Built with FastAPI, CrewAI, APScheduler, and FFmpeg.

Features:
- Connect Instagram Business/Creator accounts via OAuth
- Upload and split videos into 30-second Reel segments
- AI-powered caption generation (OpenAI, Anthropic, or Ollama)
- Schedule posts with persistent APScheduler (survives restarts)
- Edit and manage posts, segments, and schedules
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db
from backend.api.routes import router as api_router
from backend.services.scheduler_service import SchedulerService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: handles startup and shutdown events.

    - Startup: Initialize DB tables, start the persistent scheduler,
      and reload any pending posts.
    - Shutdown: Gracefully stop the scheduler.
    """
    # ── Startup ──────────────────────────────────────────────
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")

    # Initialize database tables
    init_db()
    print("📦 Database initialized")

    # Start the persistent scheduler
    scheduler = SchedulerService()
    scheduler.start()
    print("⏰ Scheduler started with persistent job store")

    # Print configuration summary
    _print_config()

    yield  # Application runs here

    # ── Shutdown ─────────────────────────────────────────────
    scheduler.shutdown()
    print("👋 Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic Instagram automation tool for scheduling and publishing reels",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────

app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint with API overview."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api": {
            "auth": "/api/auth/instagram/login",
            "accounts": "/api/auth/instagram/accounts",
            "upload": "/api/posts/upload",
            "process": "/api/posts/{upload_id}/process",
            "segments": "/api/posts/segments",
            "schedule": "/api/posts/schedule",
        },
        "status": "running",
    }


# ── Serve Frontend (optional) ──────────────────────────────
# Uncomment if you want FastAPI to serve the frontend
# app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")


def _print_config():
    """Print a summary of the current configuration."""
    print(f"\n{'='*50}")
    print(f"  {settings.APP_NAME}")
    print(f"{'='*50}")
    print(f"  Version:     {settings.APP_VERSION}")
    print(f"  Host:        {settings.HOST}:{settings.PORT}")
    print(f"  Database:    {settings.DATABASE_URL}")
    print(f"  Upload dir:  {settings.UPLOAD_DIR}")
    print(f"  Reel length: {settings.REEL_DURATION_SECONDS}s")
    print(f"  Captions:    {settings.CAPTION_PROVIDER}")
    print(f"  Instagram:   {'✅ Configured' if settings.FACEBOOK_APP_ID else '❌ Not configured'}")
    print(f"  Max upload:  {settings.MAX_UPLOAD_SIZE_MB}MB")
    print(f"{'='*50}\n")


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
