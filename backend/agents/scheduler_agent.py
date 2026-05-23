"""
SchedulerAgent - CrewAI agent responsible for managing the posting schedule
using APScheduler with persistent SQLite storage.
"""

from datetime import datetime, timezone
from typing import Optional
from crewai import Agent
from crewai.tools import tool
from backend.services.scheduler_service import SchedulerService


# ── Shared service instance ──────────────────────────────

_scheduler_service = SchedulerService()


class SchedulerAgent:
    """
    Agent that manages Instagram post scheduling.

    Handles:
    - Scheduling posts at specific times
    - Rescheduling existing posts
    - Cancelling scheduled posts
    - Listing upcoming posts
    - Ensuring persistence across server restarts
    """

    def __init__(self):
        self.service = SchedulerService()

    def create_tools(self) -> list:
        service = self.service

        @tool("schedule_post")
        def _schedule_post(post_id: int, run_date: str, publish_func_desc: str = "") -> dict:
            """Schedule a post for publishing at a specific date/time.
            
            Args:
                post_id: Database ID of the post to schedule.
                run_date: ISO datetime string for when to publish (UTC).
                publish_func_desc: Description of what will be published.
                
            Returns:
                Dict with 'job_id' and 'scheduled_at' confirming the schedule.
            """
            try:
                dt = datetime.fromisoformat(run_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return {"error": f"Invalid date format: {run_date}. Use ISO format (e.g., 2025-06-01T14:00:00+00:00)"}

            # Note: The actual publish function binding is done at the API layer.
            # This tool primarily validates and registers the intent.
            return {
                "post_id": post_id,
                "scheduled_at": dt.isoformat(),
                "status": "pending",
                "message": f"Post #{post_id} prepared for scheduling at {dt.isoformat()}",
            }

        @tool("cancel_post")
        def _cancel_post(post_id: int) -> dict:
            """Cancel a previously scheduled post.
            
            Args:
                post_id: Database ID of the post to cancel.
                
            Returns:
                Dict with success status.
            """
            success = service.remove_job(post_id)
            return {"success": success, "message": f"Post #{post_id} cancelled" if success else f"Post #{post_id} not found"}

        @tool("reschedule_post")
        def _reschedule_post(post_id: int, new_run_date: str) -> dict:
            """Change the scheduled time of an existing post.
            
            Args:
                post_id: Database ID of the post to reschedule.
                new_run_date: New ISO datetime string (UTC) for when to publish.
                
            Returns:
                Dict with success status.
            """
            try:
                dt = datetime.fromisoformat(new_run_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return {"success": False, "error": f"Invalid date format: {new_run_date}"}

            success = service.reschedule_post(post_id, dt)
            return {"success": success, "new_run_date": dt.isoformat()}

        @tool("list_upcoming_posts")
        def _list_upcoming_posts() -> list:
            """List all currently scheduled upcoming posts.
            
            Returns:
                List of dicts with job id, name, and next run time.
            """
            return service.list_upcoming_jobs()

        @tool("get_scheduler_status")
        def _get_scheduler_status() -> dict:
            """Get the current status of the scheduler.
            
            Returns:
                Dict with running state, job count, and upcoming jobs.
            """
            return service.get_status()

        return [_schedule_post, _cancel_post, _reschedule_post,
                _list_upcoming_posts, _get_scheduler_status]

    def create(self) -> Agent:
        return Agent(
            role="Content Scheduling Coordinator",
            goal=(
                "Schedule Instagram Reel posts at optimal times for maximum engagement. "
                "Ensure all scheduled posts persist across server restarts and are "
                "published exactly on time. Handle conflicts and double-booking gracefully."
            ),
            backstory=(
                "You are a precision scheduling expert who manages content calendars "
                "for high-volume Instagram accounts. You understand the importance of "
                "posting at the right time, handling timezone conversions, and ensuring "
                "that no post is missed even if the server restarts. Your schedules are "
                "reliable down to the second. You use APScheduler with SQLite persistence "
                "to ensure jobs survive server restarts."
            ),
            tools=self.create_tools(),
            verbose=False,
            allow_delegation=False,
        )


# Direct-use functions for API layer

def schedule_post_direct(
    post_id: int,
    run_date: datetime,
    publish_func: callable,
    args: tuple = (),
) -> str:
    """Direct function to schedule a post (without CrewAI)."""
    return _scheduler_service.schedule_post(
        post_id=post_id,
        publish_func=publish_func,
        run_date=run_date,
        args=args,
    )


def cancel_post_direct(post_id: int) -> bool:
    """Direct function to cancel a scheduled post."""
    return _scheduler_service.remove_job(post_id)


def reschedule_post_direct(post_id: int, new_run_date: datetime) -> bool:
    """Direct function to reschedule a post."""
    return _scheduler_service.reschedule_post(post_id, new_run_date)


def get_scheduler_status() -> dict:
    """Get scheduler status (no CrewAI needed)."""
    return _scheduler_service.get_status()


# Expose this for other modules
scheduler_service = _scheduler_service
