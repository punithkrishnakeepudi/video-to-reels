"""
Helper utility functions for ReelForge.
"""

import os
import re
import uuid
from datetime import datetime, timezone


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename while preserving extension."""
    ext = os.path.splitext(original_filename)[1] or ".mp4"
    return f"{uuid.uuid4().hex}{ext}"


def sanitize_filename(filename: str) -> str:
    """Remove potentially unsafe characters from filename."""
    sanitized = re.sub(r'[^\w\-_. ]', '', filename)
    return sanitized.strip() or "untitled"


def ensure_dir(path: str) -> str:
    """Ensure a directory exists, creating it if necessary."""
    os.makedirs(path, exist_ok=True)
    return path


def format_timestamp(dt: datetime) -> str:
    """Format a datetime for display in the UI."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def parse_datetime(dt_str: str) -> datetime:
    """Parse an ISO datetime string, returning a timezone-aware UTC datetime."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_upload_path(upload_dir: str, account_id: int, upload_id: int) -> str:
    """Generate a structured path for uploads."""
    path = os.path.join(upload_dir, str(account_id), str(upload_id))
    ensure_dir(path)
    return path


def get_segments_path(upload_dir: str, account_id: int, upload_id: int) -> str:
    """Generate a structured path for segments."""
    path = os.path.join(upload_dir, str(account_id), str(upload_id), "segments")
    ensure_dir(path)
    return path
