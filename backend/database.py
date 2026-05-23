"""
Database models for ReelForge - Instagram Automation Tool.

Uses SQLAlchemy with SQLite as the default database.
"""

import os
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
import enum

from backend.config import settings


# ── Engine & Session ────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ── Enums ───────────────────────────────────────────────────

class SegmentStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class PostStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Base ────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ──────────────────────────────────────────────────

class InstagramAccount(Base):
    """Stores connected Instagram Business/Creator accounts."""
    __tablename__ = "instagram_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    instagram_user_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(128), nullable=False)
    name = Column(String(256), default="")
    profile_pic = Column(String(512), default="")
    fb_page_id = Column(String(64), default="")
    fb_page_name = Column(String(256), default="")
    access_token = Column(Text, nullable=False)
    token_expiry = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # relationships
    video_uploads = relationship("VideoUpload", back_populates="account",
                                 cascade="all, delete-orphan")
    scheduled_posts = relationship("ScheduledPost", back_populates="account",
                                   cascade="all, delete-orphan")


class VideoUpload(Base):
    """Tracks original video uploads and their split metadata."""
    __tablename__ = "video_uploads"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    instagram_account_id = Column(Integer, ForeignKey("instagram_accounts.id"),
                                  nullable=False)
    original_filename = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False)
    duration_seconds = Column(Float, default=0.0)
    segments_count = Column(Integer, default=0)
    status = Column(String(32), default="uploaded")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # relationships
    account = relationship("InstagramAccount", back_populates="video_uploads")
    segments = relationship("VideoSegment", back_populates="video_upload",
                            cascade="all, delete-orphan")


class VideoSegment(Base):
    """Individual 30-second reel segments from a split video."""
    __tablename__ = "video_segments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_upload_id = Column(Integer, ForeignKey("video_uploads.id"), nullable=False)
    segment_index = Column(Integer, nullable=False)
    file_path = Column(String(512), nullable=False)
    start_time = Column(Float, default=0.0)
    end_time = Column(Float, default=0.0)
    duration = Column(Float, default=0.0)
    caption = Column(Text, default="")
    hashtags = Column(Text, default="")
    status = Column(String(32), default=SegmentStatus.DRAFT.value)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # relationships
    video_upload = relationship("VideoUpload", back_populates="segments")
    scheduled_posts = relationship("ScheduledPost", back_populates="segment",
                                   cascade="all, delete-orphan")


class ScheduledPost(Base):
    """Scheduled publication of a reel segment to Instagram."""
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    segment_id = Column(Integer, ForeignKey("video_segments.id"), nullable=False)
    instagram_account_id = Column(Integer, ForeignKey("instagram_accounts.id"),
                                  nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(32), default=PostStatus.PENDING.value)
    instagram_media_id = Column(String(128), default="")
    instagram_permalink = Column(String(512), default="")
    error_message = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime, nullable=True)

    # relationships
    segment = relationship("VideoSegment", back_populates="scheduled_posts")
    account = relationship("InstagramAccount", back_populates="scheduled_posts")


# ── Helpers ─────────────────────────────────────────────────

def get_db():
    """Dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call multiple times."""
    Base.metadata.create_all(bind=engine)
