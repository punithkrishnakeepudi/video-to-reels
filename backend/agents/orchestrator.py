"""
Agent Orchestrator - Coordinates the multi-agent CrewAI workflow for
end-to-end Instagram reel processing and publishing.

Workflow:
1. VideoProcessorAgent splits the uploaded video into 30-second segments
2. CaptionAgent generates AI captions and hashtags for each segment
3. SchedulerAgent manages the posting schedule
4. InstagramPublisherAgent publishes to Instagram at the scheduled time
"""

import os
from datetime import datetime, timezone
from typing import Optional
from crewai import Crew, Process, Task

from backend.agents.video_processor import VideoProcessorAgent
from backend.agents.caption_agent import CaptionAgent
from backend.agents.scheduler_agent import SchedulerAgent
from backend.agents.instagram_publisher import InstagramPublisherAgent
from backend.config import settings


class ReelForgeOrchestrator:
    """
    Orchestrates the multi-agent workflow for processing videos and
    scheduling Instagram Reel posts.

    Uses CrewAI to coordinate specialized agents in a sequential process.
    """

    def __init__(
        self,
        access_token: str = "",
        ig_user_id: str = "",
        ig_username: str = "",
    ):
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.ig_username = ig_username

    def process_and_schedule(
        self,
        video_path: str,
        output_dir: str,
        video_topic: str = "",
        schedule_times: list[datetime] = None,
        caption_style: str = "engaging",
        segment_duration: int = None,
    ) -> dict:
        """
        End-to-end workflow: split video → generate captions → schedule posts.

        This is the main entry point for the agentic pipeline.

        Args:
            video_path: Path to the uploaded video file.
            output_dir: Directory to store split segments.
            video_topic: Description of video content (for caption context).
            schedule_times: List of UTC datetimes for each segment. If None,
                           segments are only prepared, not scheduled.
            caption_style: Style for captions (engaging, professional, etc.).
            segment_duration: Duration of each segment in seconds.

        Returns:
            Dict with keys: segments (list), status, total_segments.
        """
        seg_duration = segment_duration or settings.REEL_DURATION_SECONDS

        # ── Create Agents ────────────────────────────────────
        video_agent = VideoProcessorAgent.create()

        caption_agent = CaptionAgent().create()

        scheduler_agent = SchedulerAgent().create()
        instagram_agent = InstagramPublisherAgent().create()

        # ── Define Tasks ──────────────────────────────────────

        # Task 1: Split video
        split_task = Task(
            description=(
                f"Split the video at '{video_path}' into {seg_duration}-second segments. "
                f"Save segments to '{output_dir}'. Return the list of segments with "
                f"their file paths and timestamps."
            ),
            expected_output=(
                "A list of segment dicts: [{'index': 0, 'file_path': '...', "
                "'start_time': 0.0, 'end_time': 30.0, 'duration': 30.0}, ...]"
            ),
            agent=video_agent,
        )

        # Task 2: Generate captions
        caption_task = Task(
            description=(
                f"Generate engaging {caption_style} captions and relevant hashtags "
                f"for each video segment. Video topic: '{video_topic or 'General content'}'. "
                f"There are multiple segments that are part of a series."
            ),
            expected_output=(
                "List of segment dicts with 'caption' and 'hashtags' added."
            ),
            agent=caption_agent,
        )

        # Task 3: Schedule posts (if times provided)
        schedule_task = None
        if schedule_times:
            times_str = ", ".join(t.isoformat() for t in schedule_times)
            schedule_task = Task(
                description=(
                    f"Schedule each processed segment for posting at the following "
                    f"dates/times (UTC): [{times_str}]. "
                    f"There are {len(schedule_times)} segments to schedule. "
                    f"Ensure the scheduler is running and jobs are persisted."
                ),
                expected_output=(
                    "Confirmation that all posts were scheduled successfully."
                ),
                agent=scheduler_agent,
            )

        # ── Create Crew ──────────────────────────────────────
        tasks = [split_task, caption_task]
        if schedule_task:
            tasks.append(schedule_task)

        crew = Crew(
            agents=[video_agent, caption_agent, scheduler_agent, instagram_agent],
            tasks=tasks,
            process=Process.sequential,
            verbose=False,
        )

        # ── Run ──────────────────────────────────────────────
        result = crew.kickoff()

        return {
            "result": result,
            "segments_count": len(schedule_times) if schedule_times else 0,
            "status": "completed",
        }

    def process_video_only(
        self,
        video_path: str,
        output_dir: str,
        segment_duration: int = None,
    ) -> list[dict]:
        """
        Simpler pipeline: only split video into segments (no caption/schedule).

        Useful for the API where caption generation and scheduling are done separately.
        """
        from backend.agents.video_processor import process_video_upload
        return process_video_upload(
            file_path=video_path,
            output_dir=output_dir,
        )

    def generate_captions_only(
        self,
        segments: list[dict],
        video_topic: str = "",
        style: str = "engaging",
    ) -> list[dict]:
        """Generate captions for pre-split segments."""
        from backend.agents.caption_agent import generate_captions_for_segments
        return generate_captions_for_segments(
            segments=segments,
            video_topic=video_topic,
            style=style,
        )
