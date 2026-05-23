"""
Main API router that aggregates all route modules.
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.api.auth_routes import router as auth_router
from backend.api.post_routes import router as post_router
from backend.config import settings

router = APIRouter()

# Include sub-routers
router.include_router(auth_router)
router.include_router(post_router)


@router.get("/status")
async def api_status():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "instagram_configured": bool(settings.FACEBOOK_APP_ID and settings.FACEBOOK_APP_SECRET),
    }


@router.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler status."""
    from backend.agents.scheduler_agent import scheduler_service
    return scheduler_service.get_status()


# Serve uploaded media files for Instagram to access
@router.get("/media/{account_id}/{upload_id}/{filename}")
async def serve_media(account_id: int, upload_id: int, filename: str):
    """Serve a media file (used by Instagram to fetch video for publishing)."""
    file_path = os.path.join(settings.UPLOAD_DIR, str(account_id), str(upload_id), filename)
    if not os.path.exists(file_path):
        # Try segments directory
        seg_path = os.path.join(settings.UPLOAD_DIR, str(account_id), str(upload_id), "segments", filename)
        if os.path.exists(seg_path):
            file_path = seg_path
        else:
            raise HTTPException(status_code=404, detail="File not found")

    media_type = "video/mp4"
    if filename.endswith(".mp3"):
        media_type = "audio/mpeg"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif filename.endswith(".png"):
        media_type = "image/png"

    return FileResponse(file_path, media_type=media_type)
