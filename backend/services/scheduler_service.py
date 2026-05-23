"""
Scheduler service using APScheduler with persistent SQLite job store.

Features:
- Jobs survive server restarts (SQLite persistence)
- Background execution
- Automatic retry on failures
- Supports adding, removing, listing, and rescheduling jobs
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.util import undefined
from sqlalchemy.orm import Session

from backend.config import settings


class SchedulerService:
    """
    Singleton scheduler service for managing Instagram post scheduling.

    Uses APScheduler BackgroundScheduler with SQLAlchemyJobStore
    for persistent job storage.
    """

    _instance = None
    _scheduler: Optional[BackgroundScheduler] = None
    _is_running = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def start(self):
        """Initialize and start the scheduler with persistent job store."""
        if self._is_running:
            return

        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.SCHEDULER_DB_URL)
        }
        executors = {
            "default": ThreadPoolExecutor(10),
        }
        job_defaults = {
            "coalesce": True,       # Combine missed runs into one
            "max_instances": 1,     # Only one instance at a time
            "misfire_grace_time": 3600,  # Allow up to 1 hour late
        }

        self._scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )

        self._scheduler.start()
        self._is_running = True
        print(f"[Scheduler] Started with persistent store: {settings.SCHEDULER_DB_URL}")

    def shutdown(self):
        """Shutdown the scheduler gracefully."""
        if self._scheduler and self._is_running:
            self._scheduler.shutdown(wait=True)
            self._is_running = False
            print("[Scheduler] Shutdown complete")

    @property
    def running(self) -> bool:
        return self._is_running and self._scheduler is not None

    # ── Job Management ─────────────────────────────────────

    def schedule_post(
        self,
        post_id: int,
        publish_func: Callable,
        run_date: datetime,
        args: tuple = (),
        kwargs: dict = None,
    ) -> str:
        """
        Schedule a post for publishing at a specific time.

        Args:
            post_id: Database ID of the scheduled post.
            publish_func: The function to call when publishing.
            run_date: UTC datetime when the post should be published.
            args: Positional arguments for publish_func.
            kwargs: Keyword arguments for publish_func.

        Returns:
            Job ID string.
        """
        if not self._scheduler:
            self.start()

        job_id = f"post_{post_id}"

        # Ensure run_date is timezone-aware
        if run_date.tzinfo is None:
            run_date = run_date.replace(tzinfo=timezone.utc)

        # Remove existing job with same ID if it exists
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

        self._scheduler.add_job(
            publish_func,
            trigger="date",
            run_date=run_date,
            args=args,
            kwargs=kwargs or {},
            id=job_id,
            name=f"Publish post #{post_id}",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        print(f"[Scheduler] Scheduled post #{post_id} for {run_date.isoformat()}")
        return job_id

    def remove_job(self, post_id: int) -> bool:
        """
        Remove a scheduled job.

        Args:
            post_id: Database ID of the scheduled post.

        Returns:
            True if removed, False if not found.
        """
        if not self._scheduler:
            return False

        job_id = f"post_{post_id}"
        try:
            self._scheduler.remove_job(job_id)
            print(f"[Scheduler] Removed job: post #{post_id}")
            return True
        except Exception:
            return False

    def reschedule_post(self, post_id: int, new_run_date: datetime) -> bool:
        """
        Reschedule an existing post to a new date/time.

        Args:
            post_id: Database ID of the scheduled post.
            new_run_date: New UTC datetime for publishing.

        Returns:
            True if rescheduled, False if not found.
        """
        if not self._scheduler:
            return False

        job_id = f"post_{post_id}"
        if new_run_date.tzinfo is None:
            new_run_date = new_run_date.replace(tzinfo=timezone.utc)

        try:
            self._scheduler.reschedule_job(
                job_id,
                trigger="date",
                run_date=new_run_date,
            )
            print(f"[Scheduler] Rescheduled post #{post_id} to {new_run_date.isoformat()}")
            return True
        except Exception:
            return False

    def get_job_info(self, post_id: int) -> Optional[dict]:
        """Get information about a scheduled job."""
        if not self._scheduler:
            return None

        job_id = f"post_{post_id}"
        try:
            job = self._scheduler.get_job(job_id)
            if job:
                return {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "pending": True,
                }
            return {"id": job_id, "pending": False}
        except Exception:
            return None

    def list_upcoming_jobs(self) -> list[dict]:
        """List all upcoming scheduled jobs."""
        if not self._scheduler:
            return []

        jobs = self._scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in jobs
        ]

    def get_scheduled_post_ids(self) -> set[int]:
        """Get set of post IDs that have active jobs."""
        if not self._scheduler:
            return set()

        post_ids = set()
        for job in self._scheduler.get_jobs():
            if job.id.startswith("post_"):
                try:
                    post_ids.add(int(job.id.replace("post_", "")))
                except ValueError:
                    pass
        return post_ids

    def pause_all(self):
        """Pause all scheduled jobs."""
        if self._scheduler:
            self._scheduler.pause()

    def resume_all(self):
        """Resume all paused jobs."""
        if self._scheduler:
            self._scheduler.resume()

    def get_status(self) -> dict:
        """Get scheduler status information."""
        if not self._scheduler:
            return {"running": False, "jobs_count": 0}

        jobs = self._scheduler.get_jobs()
        return {
            "running": self._is_running,
            "jobs_count": len(jobs),
            "upcoming_jobs": [
                {
                    "id": j.id,
                    "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
                }
                for j in jobs
            ],
        }
