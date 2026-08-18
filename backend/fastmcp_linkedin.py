import os
import sys
import logging
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from database import DatabaseManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_linkedin")

# Initialize FastMCP Server
mcp = FastMCP("LinkedIn Server")

# Initialize Database Manager
db = DatabaseManager()

def get_linkedin_client():
    """Helper to check if real credentials exist and are valid."""
    creds = db.get_credentials()
    if not creds:
        return None
    # Check expiry
    if creds.get('expires_at', 0) < int(datetime.utcnow().timestamp()):
        logger.warning("LinkedIn access token expired.")
        return None
    return creds

def upload_image_to_linkedin(access_token: str, author_urn: str, image_url: str) -> Optional[str]:
    """Downloads image and uploads it to LinkedIn via the Images API, returning the asset URN."""
    try:
        logger.info(f"Downloading image from: {image_url}")
        img_response = requests.get(image_url, timeout=15)
        if img_response.status_code != 200:
            logger.error(f"Failed to download image from URL. Status: {img_response.status_code}")
            return None
        image_bytes = img_response.content

        # Step 1: Initialize image upload
        init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Linkedin-Version": "202607",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        init_payload = {
            "initializeUploadRequest": {
                "owner": author_urn
            }
        }
        logger.info("Initializing image upload to LinkedIn...")
        init_res = requests.post(init_url, headers=headers, json=init_payload, timeout=15)
        if init_res.status_code != 200:
            logger.error(f"Failed to initialize image upload. Status: {init_res.status_code}, Body: {init_res.text}")
            return None

        init_data = init_res.json()
        upload_url = init_data["value"]["uploadUrl"]
        image_urn = init_data["value"]["image"]
        logger.info(f"LinkedIn image URN initialized: {image_urn}")

        # Step 2: Upload binary image data
        upload_headers = {
            "Authorization": f"Bearer {access_token}"
        }
        logger.info("Uploading image binary data...")
        upload_res = requests.put(upload_url, headers=upload_headers, data=image_bytes, timeout=30)
        if upload_res.status_code not in (200, 201, 204):
            logger.error(f"Failed to upload binary image data. Status: {upload_res.status_code}")
            return None

        logger.info("Image upload complete.")
        return image_urn
    except Exception as e:
        logger.error(f"Exception during image upload: {e}", exc_info=True)
        return None

@mcp.tool()
def publish_post(text: str, image_url: Optional[str] = None) -> str:
    """
    Publish a post to LinkedIn immediately.
    Requires active LinkedIn connection. Raises error if no credentials found.
    """
    creds = get_linkedin_client()
    
    if not creds:
        raise ValueError("Error: No active LinkedIn connection found. Please log in with LinkedIn via the dashboard first.")

    access_token = creds['access_token']
    author_urn = creds['member_urn']

    # Sandbox / Mock Mode Bypass
    if access_token.startswith("mock_"):
        import uuid
        mock_urn = f"urn:li:share:mock_{uuid.uuid4().hex[:12]}"
        post_id = db.create_post(content=text, image_url=image_url, status='published', linkedin_urn=mock_urn)
        return f"[Sandbox Mode] Post successfully published locally! LinkedIn URN: {mock_urn}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Linkedin-Version": "202607",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    media_urn = None
    if image_url:
        media_urn = upload_image_to_linkedin(access_token, author_urn, image_url)
        if not media_urn:
            logger.warning("Image upload failed. Posting text-only instead.")

    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED"
        },
        "lifecycleState": "PUBLISHED"
    }

    if media_urn:
        payload["content"] = {
            "media": {
                "title": "Attached Image",
                "id": media_urn
            }
        }

    try:
        url = "https://api.linkedin.com/rest/posts"
        logger.info(f"Publishing to LinkedIn: {payload}")
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        
        if res.status_code == 201:
            linkedin_urn = res.headers.get("x-restli-id", "urn:li:post:unknown")
            post_id = db.create_post(content=text, image_url=image_url, status='published', linkedin_urn=linkedin_urn)
            return f"[Real LinkedIn] Post successfully published! LinkedIn URN: {linkedin_urn}"
        else:
            err_msg = f"LinkedIn API error: {res.status_code} - {res.text}"
            logger.error(err_msg)
            db.create_post(content=text, image_url=image_url, status='failed')
            return f"[Real LinkedIn] Failed to publish post. Error: {err_msg}"
    except Exception as e:
        logger.error(f"Exception during LinkedIn API call: {e}")
        db.create_post(content=text, image_url=image_url, status='failed')
        return f"[Real LinkedIn] Failed to publish post due to an internal exception: {e}"

@mcp.tool()
def schedule_post(text: str, publish_time: str, image_url: Optional[str] = None) -> str:
    """
    Schedules a post to be published on LinkedIn at a future date/time.
    publish_time: ISO 8601 formatted string (e.g. '2026-08-17T21:00:00')
    """
    creds = get_linkedin_client()
    if not creds:
        raise ValueError("Error: No active LinkedIn connection found. Please log in with LinkedIn via the dashboard first.")

    try:
        # Validate timestamp
        dt = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
        dt_str = dt.isoformat()
    except ValueError as e:
        return f"Error: Invalid publish_time format. Must be ISO 8601 (e.g. YYYY-MM-DDTHH:MM:SS). Error: {e}"

    post_id = db.create_post(
        content=text, 
        image_url=image_url, 
        status='scheduled', 
        scheduled_time=dt_str
    )
    return f"Post successfully scheduled for {dt_str} (Local Post ID: {post_id})."

@mcp.tool()
def delete_post(post_id: int) -> str:
    """
    Deletes a scheduled or published post from the local database.
    If the post is published, it deletes it locally (cancelling it from view).
    """
    post = db.get_post(post_id)
    if not post:
        return f"Post with ID {post_id} not found."
        
    db.delete_post(post_id)
    return f"Successfully deleted/cancelled post {post_id}."

@mcp.tool()
def list_posts() -> List[Dict[str, Any]]:
    """
    Retrieves all scheduled, drafted, and published posts.
    """
    return db.get_posts()

if __name__ == "__main__":
    mcp.run()
