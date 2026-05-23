"""
Authentication routes for Instagram OAuth flow.

Handles:
- Generating the Facebook Login URL
- Handling the OAuth callback (code exchange)
- Token refresh
- Account listing and management
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
import httpx

from backend.database import get_db, InstagramAccount
from backend.models import (
    InstagramAccountOut, InstagramAccountList,
    InstagramAuthUrl, InstagramConnect, InstagramConnectResponse,
    MessageResponse, ErrorResponse,
)
from backend.services.instagram_client import InstagramClient
from backend.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/instagram/login", response_model=InstagramAuthUrl)
async def instagram_login(state: str = Query("", description="Optional state parameter")):
    """
    Get the Instagram/Facebook login URL for OAuth authentication.
    Users need to visit this URL to connect their Instagram account.
    """
    if not settings.FACEBOOK_APP_ID or not settings.FACEBOOK_APP_SECRET:
        return InstagramAuthUrl(
            auth_url=""
        )

    client = InstagramClient()
    auth_url = client.get_login_url(state=state)

    if not auth_url:
        raise HTTPException(
            status_code=400,
            detail="Instagram/Facebook App credentials not configured. "
                   "Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in your .env file."
        )

    return InstagramAuthUrl(auth_url=auth_url)


@router.get("/instagram/callback", response_model=InstagramConnectResponse)
async def instagram_callback(
    code: str = Query(""),
    state: str = Query(""),
    error: str = Query(None),
    error_reason: str = Query(None),
    error_description: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle the OAuth callback from Facebook Login.
    Exchanges the authorization code for an access token and
    retrieves the connected Instagram account.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Instagram authorization failed: {error_description or error}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")

    try:
        # Exchange code for short-lived token
        client = InstagramClient()
        token_data = client.exchange_code_for_token(code)
        short_lived_token = token_data.get("access_token", "")

        if not short_lived_token:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Exchange short-lived token for long-lived token (60 days)
        long_lived_data = client.exchange_token(short_lived_token)
        access_token = long_lived_data.get("access_token", short_lived_token)
        expires_in = long_lived_data.get("expires_in", 5184000)  # default 60 days

        # Set the token and discover Instagram accounts
        client.access_token = access_token
        pages = client._get_pages()

        if not pages:
            raise HTTPException(
                status_code=400,
                detail="No Facebook Pages found. You need a Facebook Page linked to "
                       "an Instagram Business/Creator account."
            )

        # Use the first page
        fb_page = pages[0]
        fb_page_id = fb_page["id"]
        fb_page_name = fb_page.get("name", "")

        # Get Instagram accounts connected to this page
        ig_accounts = client.get_instagram_accounts(fb_page_id=fb_page_id)

        if not ig_accounts:
            raise HTTPException(
                status_code=400,
                detail="No Instagram Business/Creator account linked to this Facebook Page. "
                       "Please connect an Instagram account in your Facebook Page settings."
            )

        ig_acct = ig_accounts[0]
        ig_user_id = ig_acct["id"]
        username = ig_acct.get("username", "")
        name = ig_acct.get("name", "")
        profile_pic = ig_acct.get("profile_pic", "")

        # Calculate token expiry
        token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Check if account already exists
        existing = db.query(InstagramAccount).filter(
            InstagramAccount.instagram_user_id == ig_user_id
        ).first()

        if existing:
            # Update existing account
            existing.access_token = access_token
            existing.token_expiry = token_expiry
            existing.username = username
            existing.name = name
            existing.profile_pic = profile_pic
            existing.fb_page_id = fb_page_id
            existing.fb_page_name = fb_page_name
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            account = existing
            message = "Instagram account reconnected successfully!"
        else:
            # Create new account
            account = InstagramAccount(
                instagram_user_id=ig_user_id,
                username=username,
                name=name,
                profile_pic=profile_pic,
                fb_page_id=fb_page_id,
                fb_page_name=fb_page_name,
                access_token=access_token,
                token_expiry=token_expiry,
                is_active=True,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            message = f"Instagram account @{username} connected successfully!"

        return InstagramConnectResponse(
            success=True,
            account=InstagramAccountOut.model_validate(account),
            message=message,
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Instagram API error: {e.response.text[:300]}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect Instagram account: {str(e)}"
        )


@router.get("/instagram/accounts", response_model=InstagramAccountList)
async def list_accounts(db: Session = Depends(get_db)):
    """List all connected Instagram accounts."""
    accounts = db.query(InstagramAccount).filter(
        InstagramAccount.is_active == True
    ).all()

    return InstagramAccountList(
        accounts=[InstagramAccountOut.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.get("/instagram/accounts/{account_id}", response_model=InstagramAccountOut)
async def get_account(account_id: int, db: Session = Depends(get_db)):
    """Get a specific Instagram account by ID."""
    account = db.query(InstagramAccount).filter(
        InstagramAccount.id == account_id,
        InstagramAccount.is_active == True,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return InstagramAccountOut.model_validate(account)


@router.delete("/instagram/accounts/{account_id}", response_model=MessageResponse)
async def disconnect_account(account_id: int, db: Session = Depends(get_db)):
    """Disconnect (soft-delete) an Instagram account."""
    account = db.query(InstagramAccount).filter(
        InstagramAccount.id == account_id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.is_active = False
    db.commit()

    return MessageResponse(message=f"Account @{account.username} disconnected")


@router.get("/instagram/accounts/{account_id}/refresh")
async def refresh_token(account_id: int, db: Session = Depends(get_db)):
    """Refresh the access token for an Instagram account."""
    account = db.query(InstagramAccount).filter(
        InstagramAccount.id == account_id,
        InstagramAccount.is_active == True,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        client = InstagramClient(access_token=account.access_token)
        refreshed = client.refresh_token()
        new_token = refreshed.get("access_token", account.access_token)
        expires_in = refreshed.get("expires_in", 5184000)

        account.access_token = new_token
        account.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        account.updated_at = datetime.now(timezone.utc)
        db.commit()

        return MessageResponse(message="Token refreshed successfully")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh token: {str(e)}"
        )
