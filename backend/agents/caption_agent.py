"""
CaptionAgent - CrewAI agent that generates engaging captions and hashtags
for Instagram Reels using AI-powered natural language generation.
"""

from typing import Optional
from crewai import Agent
from crewai.tools import tool
from backend.services.caption_service import CaptionService


# ── Tool Definitions ─────────────────────────────────────

_service = CaptionService()


@tool("generate_caption")
def generate_caption_tool(
    segment_index: int = 0,
    total_segments: int = 1,
    video_topic: str = "",
    style: str = "engaging",
) -> dict:
    """Generate an engaging caption and relevant hashtags for a video segment.
    
    Args:
        segment_index: Index of the segment (0-based).
        total_segments: Total number of segments in the video.
        video_topic: Description of the video content.
        style: Caption style (engaging, professional, humorous, inspirational, educational).
        
    Returns:
        Dict with 'segment_index', 'caption', and 'hashtags'.
    """
    caption, hashtags = _service.generate_caption(
        segment_index=segment_index,
        total_segments=total_segments,
        video_topic=video_topic,
        style=style,
    )
    return {
        "segment_index": segment_index,
        "caption": caption,
        "hashtags": hashtags,
    }


@tool("generate_batch_captions")
def generate_batch_captions_tool(count: int = 1, video_topic: str = "", style: str = "engaging") -> list:
    """Generate captions and hashtags for multiple video segments at once.
    
    Args:
        count: Number of segments to generate captions for.
        video_topic: Description of the video content.
        style: Caption style.
        
    Returns:
        List of dicts with 'segment_index', 'caption', 'hashtags'.
    """
    results = []
    for i in range(count):
        caption, hashtags = _service.generate_caption(
            segment_index=i,
            total_segments=count,
            video_topic=video_topic,
            style=style,
        )
        results.append({
            "segment_index": i,
            "caption": caption,
            "hashtags": hashtags,
        })
    return results


class CaptionAgent:
    """
    Agent that generates scroll-stopping captions and relevant hashtags
    for Instagram Reel segments.

    Supports multiple AI providers: OpenAI, Anthropic, Ollama, or template fallback.
    """

    def create(self) -> Agent:
        return Agent(
            role="Social Media Copywriter",
            goal=(
                "Write engaging, scroll-stopping captions and relevant hashtags "
                "for Instagram Reel segments that maximize reach and engagement. "
                "Adapt tone and style based on the content type and audience."
            ),
            backstory=(
                "You are a top-tier social media copywriter who has managed Instagram "
                "accounts with millions of followers. You know exactly what hooks viewers, "
                "what drives comments and shares, and how to use hashtags strategically. "
                "You tailor every caption to the content, audience, and platform trends. "
                "Your captions balance creativity with data-driven engagement techniques."
            ),
            tools=[generate_caption_tool, generate_batch_captions_tool],
            verbose=False,
            allow_delegation=False,
        )


# Direct-use function (without CrewAI)
def generate_captions_for_segments(
    segments: list[dict],
    video_topic: str = "",
    style: str = "engaging",
) -> list[dict]:
    """
    Generate captions for all segments directly.
    """
    for seg in segments:
        caption, hashtags = _service.generate_caption(
            segment_index=seg.get("index", 0),
            total_segments=len(segments),
            video_topic=video_topic,
            style=style,
        )
        seg["caption"] = caption
        seg["hashtags"] = hashtags
    return segments
