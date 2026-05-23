"""
VideoProcessorAgent - CrewAI agent responsible for splitting videos into
30-second Instagram Reel segments using FFmpeg.
"""

from crewai import Agent
from crewai.tools import tool
from backend.services.video_service import (
    split_video_into_segments,
    get_video_info,
    get_video_duration,
)
from backend.config import settings


# ── Tool Definitions ─────────────────────────────────────

@tool("split_video")
def split_video_tool(file_path: str, output_dir: str = "./segments") -> list:
    """Split a video file into 30-second segments using FFmpeg stream copy (no re-encoding).
    
    Args:
        file_path: Path to the input video file.
        output_dir: Directory to save the output segments.
        
    Returns:
        List of segments with index, file_path, start_time, end_time, duration.
    """
    return split_video_into_segments(
        input_path=file_path,
        output_dir=output_dir,
        segment_duration=settings.REEL_DURATION_SECONDS,
    )


@tool("analyze_video")
def analyze_video_tool(file_path: str) -> dict:
    """Get metadata about a video file including duration, resolution, codec, and fps.
    
    Args:
        file_path: Path to the video file.
        
    Returns:
        Dict with video metadata (duration, width, height, codec, bitrate, fps).
    """
    return get_video_info(file_path)


@tool("get_duration")
def get_duration_tool(file_path: str) -> float:
    """Get the duration of a video in seconds.
    
    Args:
        file_path: Path to the video file.
        
    Returns:
        Float duration in seconds.
    """
    return get_video_duration(file_path)


class VideoProcessorAgent:
    """
    Agent that processes uploaded videos by splitting them into
    configurable-duration segments (default 30 seconds) optimized for Instagram Reels.
    """

    @staticmethod
    def create() -> Agent:
        return Agent(
            role="Video Processing Specialist",
            goal=(
                "Split uploaded videos into 30-second segments optimized "
                "for Instagram Reels. Analyze video metadata for quality assurance. "
                "Ensure each segment is properly formatted and ready for publication."
            ),
            backstory=(
                "You are an expert video editor with deep knowledge of FFmpeg and video "
                "optimization. You specialize in preparing content for social media, "
                "particularly Instagram Reels. You ensure every segment is correctly "
                "timed, encoded, and ready for publishing. You work efficiently to "
                "process videos as fast as possible using stream copy (no re-encoding)."
            ),
            tools=[split_video_tool, analyze_video_tool, get_duration_tool],
            verbose=False,
            allow_delegation=False,
        )


# Direct-use function (without CrewAI)
def process_video_upload(file_path: str, output_dir: str) -> list[dict]:
    """
    Direct function to process a video upload without the full CrewAI pipeline.
    """
    info = get_video_info(file_path)
    duration = info.get("duration", 0)

    if duration <= 0:
        raise ValueError(f"Could not determine video duration for {file_path}")

    segments = split_video_into_segments(
        input_path=file_path,
        output_dir=output_dir,
        segment_duration=settings.REEL_DURATION_SECONDS,
    )

    return segments
