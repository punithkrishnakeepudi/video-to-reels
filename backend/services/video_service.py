"""
Video processing service using FFmpeg.

Handles:
- Splitting videos into configurable-duration segments (default 30s)
- Getting video metadata (duration, resolution, codec)
- Creating output directory structure
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from backend.config import settings


def get_video_duration(file_path: str) -> float:
    """
    Get video duration in seconds using ffprobe.

    Args:
        file_path: Absolute or relative path to video file.

    Returns:
        Duration in seconds as float.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to get video duration: {e}")


def get_video_info(file_path: str) -> dict:
    """
    Extract comprehensive video metadata.

    Returns:
        Dict with keys: duration, width, height, codec, bitrate, fps
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,bit_rate",
        "-show_entries", "stream=width,height,codec_name,r_frame_rate",
        "-of", "json",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        import json
        data = json.loads(result.stdout)

        info = {"duration": 0.0, "width": 0, "height": 0,
                "codec": "", "bitrate": "0", "fps": 0.0}

        if "format" in data:
            info["duration"] = float(data["format"].get("duration", 0))
            info["bitrate"] = data["format"].get("bit_rate", "0")

        if "streams" in data:
            for stream in data["streams"]:
                if stream.get("codec_type") == "video":
                    info["width"] = stream.get("width", 0)
                    info["height"] = stream.get("height", 0)
                    info["codec"] = stream.get("codec_name", "")
                    fps_str = stream.get("r_frame_rate", "0/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        info["fps"] = float(num) / float(den) if float(den) > 0 else 0
                    break

        return info
    except Exception as e:
        raise RuntimeError(f"Failed to get video info: {e}")


def split_video_into_segments(
    input_path: str,
    output_dir: str,
    segment_duration: int = None,
    prefix: str = "reel"
) -> list[dict]:
    """
    Split a video into segments of specified duration (default 30 seconds).

    Uses FFmpeg's segment muxer with stream copy (no re-encoding) for speed.

    Args:
        input_path: Path to input video file.
        output_dir: Directory to write segments into.
        segment_duration: Duration of each segment in seconds (default from config).
        prefix: Filename prefix for output segments.

    Returns:
        List of dicts: [{index, file_path, start_time, end_time, duration}, ...]
    """
    if segment_duration is None:
        segment_duration = settings.REEL_DURATION_SECONDS

    os.makedirs(output_dir, exist_ok=True)

    total_duration = get_video_duration(input_path)
    output_pattern = os.path.join(output_dir, f"{prefix}_%03d.mp4")

    # Use FFmpeg segment muxer for fast splitting
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c", "copy",           # Stream copy — no re-encoding
        "-map", "0",             # Include all streams
        "-segment_time", str(segment_duration),
        "-f", "segment",
        "-reset_timestamps", "1",
        "-avoid_negative_ts", "make_zero",
        output_pattern,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg split failed: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Video splitting timed out (>1 hour)")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg not found. Install it: sudo apt install ffmpeg")

    # Collect the generated segments
    segments = []
    index = 0
    while True:
        seg_path = os.path.join(output_dir, f"{prefix}_{index:03d}.mp4")
        if not os.path.exists(seg_path):
            break
        seg_duration = get_video_duration(seg_path)
        start = index * segment_duration
        end = min(start + seg_duration, total_duration)
        segments.append({
            "index": index,
            "file_path": seg_path,
            "start_time": round(start, 2),
            "end_time": round(end, 2),
            "duration": round(seg_duration, 2),
        })
        index += 1

    # If no segments were created (possible with some codecs), fallback to manual splitting
    if not segments:
        segments = _manual_split(input_path, output_dir, segment_duration, prefix, total_duration)

    return segments


def _manual_split(
    input_path: str,
    output_dir: str,
    segment_duration: int,
    prefix: str,
    total_duration: float
) -> list[dict]:
    """
    Fallback: manually cut segments using FFmpeg seek + duration.
    Used when segment muxer fails.
    """
    segments = []
    current_start = 0.0
    index = 0

    while current_start < total_duration:
        actual_duration = min(segment_duration, total_duration - current_start)
        if actual_duration < 1.0:
            break

        output_path = os.path.join(output_dir, f"{prefix}_{index:03d}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(current_start),
            "-i", input_path,
            "-t", str(actual_duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except Exception:
            break

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            seg_duration = get_video_duration(output_path)
            segments.append({
                "index": index,
                "file_path": output_path,
                "start_time": round(current_start, 2),
                "end_time": round(current_start + actual_duration, 2),
                "duration": round(seg_duration, 2),
            })
        index += 1
        current_start += segment_duration

    return segments


def cleanup_segments(file_paths: list[str]):
    """Remove temporary segment files."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
