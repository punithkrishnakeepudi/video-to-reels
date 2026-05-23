"""
InstagramPublisherAgent - CrewAI agent that handles publishing reels
to Instagram via the Graph API Content Publishing endpoint.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional
from crewai import Agent
from crewai.tools import tool
from backend.services.instagram_client import InstagramClient
from backend.config import settings


class InstagramPublisherAgent:
    """
    Agent responsible for publishing reel segments to Instagram.

    Handles:
    - Hosting video files for Instagram to access
    - Creating media containers
    - Publishing containers
    - Checking publish status
    - Token validation and management
    """

    def __init__(self, access_token: str = "", ig_user_id: str = "", account_username: str = ""):
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.account_username = account_username
        self.client = InstagramClient(access_token=access_token, instagram_user_id=ig_user_id)

    def create_tools(self) -> list:
        client = self.client

        @tool("create_reel_container")
        def _create_reel_container(video_url: str, caption: str = "", share_to_feed: bool = True) -> str:
            """Create an Instagram Reel media container (step 1 of publishing).
            
            Args:
                video_url: Public URL of the video file accessible by Instagram's servers.
                caption: Caption text for the reel (max 2200 characters).
                share_to_feed: Whether to share to the main feed (default True).
                
            Returns:
                Container ID (str) to use in the publish step.
            """
            return client.create_reel_container(
                video_url=video_url,
                caption=caption,
                share_to_feed=share_to_feed,
            )

        @tool("publish_container")
        def _publish_container(creation_id: str) -> str:
            """Publish a previously created media container (step 2 of publishing).
            
            Args:
                creation_id: The container ID returned from create_reel_container.
                
            Returns:
                Instagram media ID (str) of the published post.
            """
            return client.publish_container(creation_id=creation_id)

        @tool("check_container_status")
        def _check_container_status(container_id: str) -> dict:
            """Check the status of a media container.
            
            Args:
                container_id: The container ID to check.
                
            Returns:
                Dict with status_code and error_message if any.
            """
            return client.get_container_status(container_id)

        @tool("check_publishing_limit")
        def _check_publishing_limit() -> dict:
            """Check the remaining daily publishing quota (max 100 posts/day).
            
            Returns:
                Dict with quota usage information.
            """
            return client.check_publishing_limit()

        @tool("get_account_info")
        def _get_account_info() -> dict:
            """Get current Instagram account info: username, followers, media_count.
            
            Returns:
                Dict with account metadata.
            """
            return client.get_account_info()

        return [_create_reel_container, _publish_container, _check_container_status,
                _check_publishing_limit, _get_account_info]

    def create(self) -> Agent:
        tools = self.create_tools()
        username = self.account_username or self.ig_user_id or "Unknown"
        return Agent(
            role="Instagram Publishing Specialist",
            goal=(
                f"Publish reel segments to Instagram account @{username} "
                "on schedule. Ensure each post meets Instagram's content requirements, "
                "handle API rate limits gracefully, and verify successful publication."
            ),
            backstory=(
                "You are an expert in the Instagram Graph API content publishing pipeline. "
                "You know the two-step container creation and publishing process inside out. "
                "You handle rate limits (100 posts/day), token refreshes, container status "
                "checks, and error recovery automatically. You ensure every post goes live "
                "successfully and is properly tracked."
            ),
            tools=tools,
            verbose=False,
            allow_delegation=False,
        )


# ── Direct Publishing Function (used by scheduler) ──────────

def publish_reel_direct(
    segment_path: str,
    caption: str,
    hashtags: str,
    access_token: str,
    ig_user_id: str,
    post_id: Optional[int] = None,
) -> dict:
    """
    Direct function to publish a reel to Instagram.
    Called by APScheduler when a scheduled time is reached.

    Args:
        segment_path: Local path to the video segment.
        caption: Caption text.
        hashtags: Hashtags string.
        access_token: Instagram access token.
        ig_user_id: Instagram user ID.
        post_id: Database post ID (for logging).

    Returns:
        Dict with status, media_id, permalink, error.
    """
    client = InstagramClient(access_token=access_token, instagram_user_id=ig_user_id)
    result = {"success": False, "media_id": "", "permalink": "", "error": ""}

    try:
        video_url = _get_public_video_url(segment_path, post_id)
        full_caption = f"{caption}\n\n{hashtags}"[:2200]  # Instagram limit

        # Step 1: Create media container
        print(f"[Publisher] Creating reel container for post #{post_id}...")
        container_id = client.create_reel_container(
            video_url=video_url,
            caption=full_caption,
            share_to_feed=True,
        )

        # Step 2: Wait briefly for processing
        time.sleep(2)

        # Step 3: Publish
        print(f"[Publisher] Publishing container {container_id}...")
        media_id = client.publish_container(creation_id=container_id)

        # Step 4: Get permalink
        try:
            media_info = client.get_media_info(media_id)
            permalink = media_info.get("permalink", "")
        except Exception:
            permalink = ""

        result.update({
            "success": True,
            "media_id": media_id,
            "permalink": permalink,
        })
        print(f"[Publisher] Post #{post_id} published successfully! Media ID: {media_id}")

    except Exception as e:
        error_msg = str(e)[:500]
        result["error"] = error_msg
        print(f"[Publisher] Failed to publish post #{post_id}: {error_msg}")

    return result


def _get_public_video_url(segment_path: str, post_id: Optional[int] = None) -> str:
    """
    Get a publicly accessible URL for a video segment file.

    For local development, this assumes the file is served via FastAPI.
    For production, this should point to a CDN or cloud storage.

    The URL must be accessible by Instagram's servers for the API to work.
    """
    public_base = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    filename = os.path.basename(segment_path)
    relative_path = segment_path.replace(settings.UPLOAD_DIR, "").lstrip("/")
    return f"{public_base}/media/{relative_path}" if not relative_path.startswith("http") else relative_path
