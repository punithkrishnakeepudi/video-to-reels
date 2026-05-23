"""
Post management API routes.

Handles:
- Video upload and analysis
- Video splitting into segments
- Caption editing and regeneration
- Schedule creation and management
- Post deletion
- Listing all posts and schedules
"""

import os
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.database import get_db, InstagramAccount, VideoUpload, VideoSegment, ScheduledPost
from backend.models import (
    VideoUploadOut, VideoUploadList,
    VideoSegmentOut, VideoSegmentList, SegmentUpdate,
    ScheduledPostOut, ScheduledPostList, ScheduleCreate, ScheduleUpdate,
    UploadResponse, ProcessResponse, CaptionRegenerateRequest,
    CaptionRegenerateResponse, MessageResponse,
)
from backend.services.video_service import get_video_info, split_video_into_segments
from backend.services.caption_service import CaptionService
from backend.services.scheduler_service import SchedulerService
from backend.agents.instagram_publisher import publish_reel_direct
from backend.config import settings
from backend.utils.helpers import (
    generate_unique_filename, ensure_dir, get_upload_path, get_segments_path,
)

router = APIRouter(prefix="/api/posts", tags=["Posts"])

scheduler = SchedulerService()
caption_service = CaptionService()


# ── Video Upload ───────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    instagram_account_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload a video file and analyze its metadata.
    The video is saved to disk and its duration is extracted.
    """
    # Verify account exists
    account = db.query(InstagramAccount).filter(
        InstagramAccount.id == instagram_account_id,
        InstagramAccount.is_active == True,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Instagram account not found")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Check file extension
    allowed_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported: {', '.join(allowed_extensions)}"
        )

    # Save file
    unique_name = generate_unique_filename(file.filename)
    upload_dir = get_upload_path(settings.UPLOAD_DIR, instagram_account_id, 0)
    file_path = os.path.join(upload_dir, unique_name)

    ensure_dir(upload_dir)

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    with open(file_path, "wb") as f:
        f.write(content)

    # Get video duration
    try:
        info = get_video_info(file_path)
        duration = info.get("duration", 0)
    except Exception as e:
        # Clean up on error
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Could not analyze video: {str(e)}")

    if duration <= 0:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Could not determine video duration")

    # Create database record
    video_upload = VideoUpload(
        instagram_account_id=instagram_account_id,
        original_filename=file.filename,
        file_path=file_path,
        duration_seconds=duration,
        segments_count=0,
        status="uploaded",
    )
    db.add(video_upload)
    db.commit()
    db.refresh(video_upload)

    # Move file to proper path with upload ID
    proper_path = os.path.join(
        settings.UPLOAD_DIR, str(instagram_account_id), str(video_upload.id),
        unique_name
    )
    ensure_dir(os.path.dirname(proper_path))
    shutil.move(file_path, proper_path)
    video_upload.file_path = proper_path
    db.commit()

    return UploadResponse(
        upload=VideoUploadOut.model_validate(video_upload),
        message=f"Video uploaded successfully. Duration: {duration:.1f}s",
    )


@router.post("/{upload_id}/process", response_model=ProcessResponse)
async def process_video(
    upload_id: int,
    segment_duration: int = Form(settings.REEL_DURATION_SECONDS),
    generate_captions: bool = Form(True),
    caption_style: str = Form("engaging"),
    video_topic: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    Process an uploaded video into segments and optionally generate captions.

    Steps:
    1. Split video into {segment_duration}-second chunks
    2. (Optional) Generate AI captions for each segment
    """
    video_upload = db.query(VideoUpload).filter(VideoUpload.id == upload_id).first()
    if not video_upload:
        raise HTTPException(status_code=404, detail="Video upload not found")

    if video_upload.status != "uploaded":
        raise HTTPException(
            status_code=400,
            detail=f"Video already processed (status: {video_upload.status})"
        )

    if not os.path.exists(video_upload.file_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    # Create output directory for segments
    seg_dir = get_segments_path(
        settings.UPLOAD_DIR,
        video_upload.instagram_account_id,
        video_upload.id,
    )

    # Split video into segments
    try:
        segments_data = split_video_into_segments(
            input_path=video_upload.file_path,
            output_dir=seg_dir,
            segment_duration=segment_duration,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")

    if not segments_data:
        raise HTTPException(status_code=500, detail="No segments were created from the video")

    # Generate captions if requested
    if generate_captions:
        for seg in segments_data:
            caption, hashtags = caption_service.generate_caption(
                segment_index=seg["index"],
                total_segments=len(segments_data),
                video_topic=video_topic,
                style=caption_style,
            )
            seg["caption"] = caption
            seg["hashtags"] = hashtags

    # Create database records for segments
    db_segments = []
    for seg in segments_data:
        db_seg = VideoSegment(
            video_upload_id=video_upload.id,
            segment_index=seg["index"],
            file_path=seg["file_path"],
            start_time=seg["start_time"],
            end_time=seg["end_time"],
            duration=seg["duration"],
            caption=seg.get("caption", ""),
            hashtags=seg.get("hashtags", ""),
            status="ready",
        )
        db.add(db_seg)
        db_segments.append(db_seg)

    # Update the upload record
    video_upload.status = "processed"
    video_upload.segments_count = len(segments_data)
    db.commit()

    # Refresh segments to get IDs
    for db_seg in db_segments:
        db.refresh(db_seg)

    return ProcessResponse(
        segments=[VideoSegmentOut.model_validate(s) for s in db_segments],
        message=f"Video split into {len(db_segments)} segments with captions",
    )


# ── Segment Management ─────────────────────────────────────

@router.get("/segments", response_model=VideoSegmentList)
async def list_segments(
    upload_id: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List video segments with optional filters."""
    query = db.query(VideoSegment)

    if upload_id:
        query = query.filter(VideoSegment.video_upload_id == upload_id)
    if account_id:
        query = query.join(VideoUpload).filter(
            VideoUpload.instagram_account_id == account_id
        )
    if status:
        query = query.filter(VideoSegment.status == status)

    query = query.order_by(VideoSegment.video_upload_id, VideoSegment.segment_index)
    segments = query.all()

    return VideoSegmentList(
        segments=[VideoSegmentOut.model_validate(s) for s in segments],
        total=len(segments),
    )


@router.get("/segments/{segment_id}", response_model=VideoSegmentOut)
async def get_segment(segment_id: int, db: Session = Depends(get_db)):
    """Get a specific video segment."""
    segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return VideoSegmentOut.model_validate(segment)


@router.patch("/segments/{segment_id}", response_model=VideoSegmentOut)
async def update_segment(
    segment_id: int,
    update: SegmentUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a video segment's caption, hashtags, or status.
    Used for editing captions before scheduling.
    """
    segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    if update.caption is not None:
        segment.caption = update.caption
    if update.hashtags is not None:
        segment.hashtags = update.hashtags
    if update.status is not None:
        segment.status = update.status

    db.commit()
    db.refresh(segment)
    return VideoSegmentOut.model_validate(segment)


@router.post("/segments/{segment_id}/regenerate-caption", response_model=CaptionRegenerateResponse)
async def regenerate_caption(
    segment_id: int,
    request: CaptionRegenerateRequest,
    db: Session = Depends(get_db),
):
    """Regenerate the caption for a specific segment with a different style or custom prompt."""
    segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Get total segments count for context
    total_segments = db.query(VideoSegment).filter(
        VideoSegment.video_upload_id == segment.video_upload_id
    ).count()

    caption, hashtags = caption_service.generate_caption(
        segment_index=segment.segment_index,
        total_segments=total_segments,
        video_topic="",
        style=request.style or "engaging",
        custom_prompt=request.custom_prompt,
    )

    segment.caption = caption
    segment.hashtags = hashtags
    db.commit()
    db.refresh(segment)

    return CaptionRegenerateResponse(
        segment_id=segment.id,
        caption=caption,
        hashtags=hashtags,
    )


@router.delete("/segments/{segment_id}", response_model=MessageResponse)
async def delete_segment(segment_id: int, db: Session = Depends(get_db)):
    """Delete a video segment and its associated files."""
    segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Delete the file
    try:
        if os.path.exists(segment.file_path):
            os.remove(segment.file_path)
    except OSError:
        pass

    # Delete associated scheduled posts
    db.query(ScheduledPost).filter(
        ScheduledPost.segment_id == segment_id
    ).delete()

    db.delete(segment)
    db.commit()

    return MessageResponse(message=f"Segment {segment_id} deleted")


# ── Schedule Management ────────────────────────────────────

@router.post("/schedule", response_model=ScheduledPostOut)
async def schedule_post(
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
):
    """
    Schedule a video segment for posting at a specific time.

    The scheduler uses APScheduler with SQLite persistence, so
    scheduled posts will survive server restarts.
    """
    # Verify segment
    segment = db.query(VideoSegment).filter(VideoSegment.id == schedule.segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Verify account
    account = db.query(InstagramAccount).filter(
        InstagramAccount.id == schedule.instagram_account_id,
        InstagramAccount.is_active == True,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Instagram account not found")

    # Validate schedule time
    schedule_time = schedule.scheduled_at
    if schedule_time.tzinfo is None:
        schedule_time = schedule_time.replace(tzinfo=timezone.utc)

    # Allow scheduling up to 60 days in advance (Instagram token limit)
    max_future = datetime.now(timezone.utc) + timedelta(days=60)
    if schedule_time > max_future:
        raise HTTPException(
            status_code=400,
            detail="Cannot schedule more than 60 days in advance"
        )

    # Don't allow scheduling in the past
    if schedule_time < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Cannot schedule in the past"
        )

    # Create scheduled post record
    scheduled = ScheduledPost(
        segment_id=segment.id,
        instagram_account_id=account.id,
        scheduled_at=schedule_time,
        status="pending",
    )
    db.add(scheduled)
    db.commit()
    db.refresh(scheduled)

    # Schedule with APScheduler (persistent)
    try:
        scheduler.schedule_post(
            post_id=scheduled.id,
            publish_func=publish_reel_direct,
            run_date=schedule_time,
            args=(
                segment.file_path,
                segment.caption,
                segment.hashtags,
                account.access_token,
                account.instagram_user_id,
                scheduled.id,
            ),
        )
    except Exception as e:
        # If scheduler fails, mark as failed
        scheduled.status = "failed"
        scheduled.error_message = f"Scheduling error: {str(e)}"
        db.commit()

    db.refresh(scheduled)
    return ScheduledPostOut.model_validate(scheduled)


@router.get("/schedule", response_model=ScheduledPostList)
async def list_scheduled_posts(
    account_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    include_past: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List scheduled posts with optional filters."""
    query = db.query(ScheduledPost)

    if account_id:
        query = query.filter(ScheduledPost.instagram_account_id == account_id)
    if status:
        query = query.filter(ScheduledPost.status == status)
    if not include_past:
        query = query.filter(
            ScheduledPost.scheduled_at >= datetime.now(timezone.utc)
        )

    query = query.order_by(ScheduledPost.scheduled_at.asc())
    posts = query.all()

    return ScheduledPostList(
        posts=[ScheduledPostOut.model_validate(p) for p in posts],
        total=len(posts),
    )


@router.get("/schedule/{post_id}", response_model=ScheduledPostOut)
async def get_scheduled_post(post_id: int, db: Session = Depends(get_db)):
    """Get a specific scheduled post."""
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    return ScheduledPostOut.model_validate(post)


@router.patch("/schedule/{post_id}", response_model=ScheduledPostOut)
async def update_scheduled_post(
    post_id: int,
    update: ScheduleUpdate,
    db: Session = Depends(get_db),
):
    """Update a scheduled post's time or status."""
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    if update.scheduled_at is not None:
        new_time = update.scheduled_at
        if new_time.tzinfo is None:
            new_time = new_time.replace(tzinfo=timezone.utc)

        post.scheduled_at = new_time

        # Reschedule in APScheduler
        success = scheduler.reschedule_post(post_id, new_time)
        if not success:
            # Re-create the job
            account = db.query(InstagramAccount).filter(
                InstagramAccount.id == post.instagram_account_id
            ).first()
            segment = db.query(VideoSegment).filter(
                VideoSegment.id == post.segment_id
            ).first()
            if account and segment:
                scheduler.schedule_post(
                    post_id=post.id,
                    publish_func=publish_reel_direct,
                    run_date=new_time,
                    args=(
                        segment.file_path,
                        segment.caption,
                        segment.hashtags,
                        account.access_token,
                        account.instagram_user_id,
                        post.id,
                    ),
                )

    if update.status is not None:
        post.status = update.status
        if update.status == "cancelled":
            scheduler.remove_job(post_id)

    db.commit()
    db.refresh(post)
    return ScheduledPostOut.model_validate(post)


@router.delete("/schedule/{post_id}", response_model=MessageResponse)
async def delete_scheduled_post(post_id: int, db: Session = Depends(get_db)):
    """Delete/cancel a scheduled post."""
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")

    # Remove from scheduler
    scheduler.remove_job(post_id)

    db.delete(post)
    db.commit()

    return MessageResponse(message=f"Scheduled post {post_id} cancelled and deleted")


# ── Upload Management ──────────────────────────────────────

@router.get("/uploads", response_model=VideoUploadList)
async def list_uploads(
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List all video uploads."""
    query = db.query(VideoUpload)
    if account_id:
        query = query.filter(VideoUpload.instagram_account_id == account_id)

    query = query.order_by(VideoUpload.created_at.desc())
    uploads = query.all()

    return VideoUploadList(
        uploads=[VideoUploadOut.model_validate(u) for u in uploads],
        total=len(uploads),
    )


@router.get("/uploads/{upload_id}", response_model=VideoUploadOut)
async def get_upload(upload_id: int, db: Session = Depends(get_db)):
    """Get a specific video upload."""
    upload = db.query(VideoUpload).filter(VideoUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    return VideoUploadOut.model_validate(upload)


@router.delete("/uploads/{upload_id}", response_model=MessageResponse)
async def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    """Delete a video upload and all its segments and scheduled posts."""
    upload = db.query(VideoUpload).filter(VideoUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Clean up files
    upload_dir = os.path.dirname(upload.file_path)
    try:
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
    except OSError:
        pass

    # Delete associated scheduled posts
    for segment in upload.segments:
        db.query(ScheduledPost).filter(
            ScheduledPost.segment_id == segment.id
        ).delete()

    db.delete(upload)
    db.commit()

    return MessageResponse(message=f"Upload {upload_id} and all associated data deleted")
