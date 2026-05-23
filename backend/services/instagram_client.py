"""
Instagram Graph API client for posting reels and managing accounts.

Handles:
- OAuth token exchange and refresh
- Media container creation (photo, video, reel)
- Media publishing
- Account info retrieval
- Token validation and refresh
"""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx

from backend.config import settings


class InstagramClient:
    """
    Client for Instagram Graph API (Content Publishing).

    Requires:
    - Facebook App with Instagram Graph API enabled
    - Instagram Business/Creator account linked to a Facebook Page
    """

    GRAPH_URL = settings.INSTAGRAM_GRAPH_URL
    API_VERSION = settings.INSTAGRAM_API_VERSION

    def __init__(self, access_token: str = "", instagram_user_id: str = ""):
        self.access_token = access_token
        self.instagram_user_id = instagram_user_id
        self._client = httpx.Client(timeout=30.0)

    # ── Authentication ──────────────────────────────────────

    @staticmethod
    def get_login_url(state: str = "") -> str:
        """
        Generate Facebook Login URL for Instagram Business integration.
        User must have an Instagram Business/Creator account linked to a Facebook Page.
        """
        if not settings.FACEBOOK_APP_ID:
            return ""

        redirect_uri = settings.FACEBOOK_REDIRECT_URI
        scopes = [
            "instagram_basic",
            "instagram_content_publish",
            "pages_read_engagement",
            "pages_show_list",
        ]

        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "redirect_uri": redirect_uri,
            "scope": ",".join(scopes),
            "response_type": "code",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://www.facebook.com/{settings.INSTAGRAM_API_VERSION}/dialog/oauth?{query}"

    def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange OAuth authorization code for a short-lived access token.

        Args:
            code: The authorization code from the OAuth redirect.

        Returns:
            Dict with access_token, token_type, expires_in
        """
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/oauth/access_token"
        params = {
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
            "code": code,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def exchange_token(self, short_lived_token: str) -> dict:
        """
        Exchange short-lived token (1-2 hours) for long-lived token (60 days).

        Args:
            short_lived_token: The short-lived access token.

        Returns:
            Dict with access_token, token_type, expires_in
        """
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "fb_exchange_token": short_lived_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def refresh_token(self) -> dict:
        """
        Check if token is still valid and get current expiry.
        Long-lived tokens last 60 days and can be refreshed once every 24 hours.
        """
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.FACEBOOK_APP_ID,
            "client_secret": settings.FACEBOOK_APP_SECRET,
            "fb_exchange_token": self.access_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def debug_token(self) -> dict:
        """Get token metadata: expiry, scopes, app_id, etc."""
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/debug_token"
        params = {
            "input_token": self.access_token,
            "access_token": f"{settings.FACEBOOK_APP_ID}|{settings.FACEBOOK_APP_SECRET}",
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ── Account Info ────────────────────────────────────────

    def get_instagram_accounts(self, fb_page_id: str = "") -> list[dict]:
        """
        Get Instagram Business accounts connected to a Facebook Page.
        If fb_page_id is empty, first fetch accessible pages.

        Returns:
            List of {id, username, name, profile_pic, ...}
        """
        if not fb_page_id:
            pages = self._get_pages()
            if not pages:
                return []
            # Use the first page by default
            fb_page_id = pages[0]["id"]

        url = f"{self.GRAPH_URL}/{fb_page_id}"
        params = {
            "fields": "instagram_business_account{id,username,name,profile_picture_url}",
            "access_token": self.access_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        ig_account = data.get("instagram_business_account")
        if ig_account:
            return [{
                "id": ig_account["id"],
                "username": ig_account.get("username", ""),
                "name": ig_account.get("name", ""),
                "profile_pic": ig_account.get("profile_picture_url", ""),
                "fb_page_id": fb_page_id,
            }]
        return []

    def _get_pages(self) -> list[dict]:
        """Get Facebook Pages accessible with the current token."""
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/me/accounts"
        params = {"access_token": self.access_token}
        response = self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    def get_account_info(self) -> dict:
        """Get Instagram account info."""
        if not self.instagram_user_id:
            return {}
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{self.instagram_user_id}"
        params = {
            "fields": "id,username,name,profile_picture_url,followers_count,media_count",
            "access_token": self.access_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ── Content Publishing ──────────────────────────────────

    def create_reel_container(
        self,
        video_url: str,
        caption: str = "",
        thumbnail_url: str = "",
        share_to_feed: bool = True,
    ) -> str:
        """
        Create a Reel media container (step 1 of 2).

        Args:
            video_url: Publicly accessible URL of the video.
            caption: Caption text (up to 2200 characters).
            thumbnail_url: Optional custom thumbnail URL.
            share_to_feed: Whether to share to the main feed.

        Returns:
            Container ID (creation_id) to use in publish step.
        """
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{self.instagram_user_id}/media"
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
            "access_token": self.access_token,
        }
        if thumbnail_url:
            params["thumbnail_url"] = thumbnail_url

        response = self._client.post(url, data=params)
        response.raise_for_status()
        return response.json().get("id", "")

    def create_video_container(
        self,
        video_url: str,
        caption: str = "",
        thumbnail_url: str = "",
    ) -> str:
        """
        Create a standard video/IGTV media container.

        Args:
            video_url: Publicly accessible URL of the video.
            caption: Caption text.
            thumbnail_url: Optional custom thumbnail.

        Returns:
            Container ID for publishing.
        """
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{self.instagram_user_id}/media"
        params = {
            "media_type": "VIDEO",
            "video_url": video_url,
            "caption": caption,
            "access_token": self.access_token,
        }
        if thumbnail_url:
            params["thumbnail_url"] = thumbnail_url

        response = self._client.post(url, data=params)
        response.raise_for_status()
        return response.json().get("id", "")

    def publish_container(self, creation_id: str) -> str:
        """
        Publish a media container (step 2 of 2).

        Args:
            creation_id: The container ID from create_reel_container or create_video_container.

        Returns:
            Instagram Media ID.
        """
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{self.instagram_user_id}/media_publish"
        params = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }
        response = self._client.post(url, data=params)
        response.raise_for_status()
        return response.json().get("id", "")

    def get_container_status(self, container_id: str) -> dict:
        """Check the status of a media container."""
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{container_id}"
        params = {
            "fields": "status_code,error_message",
            "access_token": self.access_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_media_info(self, media_id: str) -> dict:
        """Get published media info."""
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{media_id}"
        params = {
            "fields": "id,media_type,media_url,permalink,caption,timestamp,like_count,comments_count",
            "access_token": self.access_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ── Resumable Upload (for large files) ──────────────────

    def upload_video_file(self, file_path: str, video_name: str = "") -> str:
        """
        Upload a video file using Facebook's resumable upload protocol.
        Use this for videos larger than ~50MB.

        Args:
            file_path: Local path to video file.
            video_name: Name for the video.

        Returns:
            Video ID after upload completion.
        """
        import os

        file_size = os.path.getsize(file_path)
        file_name = video_name or os.path.basename(file_path)

        # Step 1: Create upload session
        url = f"https://rupload.facebook.com/ig-api-upload/{self.instagram_user_id}/video"
        headers = {
            "Authorization": f"OAuth {self.access_token}",
            "upload_phase": "start",
            "file_size": str(file_size),
        }
        params = {"file_name": file_name}

        response = self._client.post(url, headers=headers, params=params)
        response.raise_for_status()
        upload_data = response.json()

        # Step 2: Upload in chunks
        upload_id = upload_data.get("id", "")
        chunk_size = 10 * 1024 * 1024  # 10MB chunks

        with open(file_path, "rb") as f:
            offset = 0
            while offset < file_size:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                headers = {
                    "Authorization": f"OAuth {self.access_token}",
                    "upload_phase": "transfer",
                    "upload_offset": str(offset),
                    "file_size": str(file_size),
                }
                upload_url = f"https://rupload.facebook.com/ig-api-upload/{self.instagram_user_id}/video?id={upload_id}"

                response = self._client.post(upload_url, headers=headers, content=chunk)
                response.raise_for_status()
                offset += len(chunk)

        # Step 3: Finish upload
        headers = {
            "Authorization": f"OAuth {self.access_token}",
            "upload_phase": "finish",
            "file_size": str(file_size),
        }
        finish_url = f"https://rupload.facebook.com/ig-api-upload/{self.instagram_user_id}/video?id={upload_id}"

        response = self._client.post(finish_url, headers=headers)
        response.raise_for_status()
        return response.json().get("video_id", "")

    def check_publishing_limit(self) -> dict:
        """Check the 24-hour publishing limit for the account (max 100 posts/day)."""
        url = f"{self.GRAPH_URL}/{self.API_VERSION}/{self.instagram_user_id}/content_publishing_limit"
        params = {
            "fields": "config,quota_usage",
            "access_token": self.access_token,
        }
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def check_rate_limit_remaining(self) -> int:
        """Estimate remaining daily posts (max 100)."""
        try:
            limit_data = self.check_publishing_limit()
            quota = limit_data.get("data", [{}])[0].get("quota_usage", 0)
            return 100 - quota
        except Exception:
            return 0
