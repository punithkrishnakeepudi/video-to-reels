"""
Pydantic schemas for ReelForge API request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Instagram Account ───────────────────────────────────────

class InstagramAccountOut(BaseModel):
    id: int
    instagram_user_id: str
    username: str
    name: str
    profile_pic: str
    fb_page_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InstagramAccountList(BaseModel):
    accounts: list[InstagramAccountOut]
    total: int


# ── Video Upload ────────────────────────────────────────────

class VideoUploadOut(BaseModel):
    id: int
    instagram_account_id: int
    original_filename: str
    duration_seconds: float
    segments_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoUploadList(BaseModel):
    uploads: list[VideoUploadOut]
    total: int


# ── Video Segment ───────────────────────────────────────────

class SegmentUpdate(BaseModel):
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    status: Optional[str] = None


class VideoSegmentOut(BaseModel):
    id: int
    video_upload_id: int
    segment_index: int
    file_path: str
    start_time: float
    end_time: float
    duration: float
    caption: str
    hashtags: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoSegmentList(BaseModel):
    segments: list[VideoSegmentOut]
    total: int


# ── Scheduled Posts ─────────────────────────────────────────

class ScheduleCreate(BaseModel):
    segment_id: int
    instagram_account_id: int
    scheduled_at: datetime


class ScheduleUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class ScheduledPostOut(BaseModel):
    id: int
    segment_id: int
    instagram_account_id: int
    scheduled_at: datetime
    status: str
    instagram_media_id: str
    instagram_permalink: str
    error_message: str
    retry_count: int
    created_at: datetime
    published_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ScheduledPostList(BaseModel):
    posts: list[ScheduledPostOut]
    total: int


# ── Auth / Connect ──────────────────────────────────────────

class InstagramAuthUrl(BaseModel):
    auth_url: str


class InstagramConnect(BaseModel):
    code: str


class InstagramConnectResponse(BaseModel):
    success: bool
    account: InstagramAccountOut
    message: str


# ── Upload / Process ────────────────────────────────────────

class UploadResponse(BaseModel):
    upload: VideoUploadOut
    message: str


class ProcessResponse(BaseModel):
    segments: list[VideoSegmentOut]
    message: str


class CaptionRegenerateRequest(BaseModel):
    style: Optional[str] = Field(default="engaging",
                                  description="Style: engaging, professional, humorous, inspirational, custom")
    custom_prompt: Optional[str] = None


class CaptionRegenerateResponse(BaseModel):
    segment_id: int
    caption: str
    hashtags: str


# ── Generic ─────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    detail: str
    success: bool = False
