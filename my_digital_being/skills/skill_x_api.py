"""X (Twitter) API integration skill."""

import os
import logging
from typing import Dict, Any, Optional
import requests
from requests_oauthlib import OAuth1Session
from framework.skill_config import SkillConfig
from framework.api_management import api_manager

logger = logging.getLogger(__name__)


class XAPIError(Exception):
    """Custom exception for X API errors"""

    pass


class XAPISkill:
    """Skill for interacting with X (Twitter) API."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize skill configuration."""
        self.config = config
        self.enabled = config.get("enabled", False)
        self.rate_limit = config.get("rate_limit", 100)
        self.cooldown_period = config.get("cooldown_period", 300)
        self.posts_count = 0
        self.skill_config = SkillConfig("twitter_posting")
        self.oauth_session: Optional[OAuth1Session] = None

    async def initialize(self) -> bool:
        """Initialize the X API skill with required credentials."""
        try:
            # Register required API keys
            required_keys = [
                "API_KEY",
                "API_SECRET",
                "ACCESS_TOKEN",
                "ACCESS_TOKEN_SECRET",
            ]
            api_manager.register_required_keys("twitter_posting", required_keys)

            # Check for missing credentials
            missing_keys = []
            for key in required_keys:
                if not self.skill_config.get_api_key(key):
                    missing_keys.append(key)

            if missing_keys:
                logger.info(f"Missing X API credentials: {missing_keys}")
                return False  # Let the front-end handle credential requests

            # Try to authenticate if we have all credentials
            return await self.authenticate()

        except Exception as e:
            logger.error(f"Failed to initialize X API skill: {e}")
            return False

    def can_post(self) -> bool:
        """Check if posting is allowed based on rate limits."""
        return self.enabled and self.posts_count < self.rate_limit

    async def authenticate(self) -> bool:
        """Set up OAuth session for X API."""
        try:
            api_key = self.skill_config.get_api_key("API_KEY")
            api_secret = self.skill_config.get_api_key("API_SECRET")
            access_token = self.skill_config.get_api_key("ACCESS_TOKEN")
            access_token_secret = self.skill_config.get_api_key("ACCESS_TOKEN_SECRET")

            if not all([api_key, api_secret, access_token, access_token_secret]):
                logger.error("Missing required X API credentials")
                return False

            self.oauth_session = OAuth1Session(
                client_key=api_key,
                client_secret=api_secret,
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def post_tweet(
        self, text: str, media_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Post a tweet with optional media attachment."""
        if not self.can_post():
            return {"success": False, "error": "Rate limit exceeded or skill disabled"}

        if not self.oauth_session:
            if not await self.authenticate():
                return {"success": False, "error": "Authentication failed"}

        try:
            # Handle media upload if provided
            media_id = None
            if media_path and os.path.exists(media_path):
                media_id = await self._upload_media(media_path)

            # Prepare tweet payload
            post_payload = {"text": text}
            if media_id:
                post_payload["media"] = {"media_ids": [media_id]}

            # Post tweet
            response = self.oauth_session.post(
                "https://api.twitter.com/2/tweets", json=post_payload
            )

            if response.status_code != 201:
                error_data = response.json() if response.text else {}
                raise XAPIError(f"Failed to post tweet: {error_data}")

            self.posts_count += 1
            return {
                "success": True,
                "tweet_id": response.json()["data"]["id"],
                "content": text,
            }

        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            return {"success": False, "error": str(e)}

    async def _upload_media(self, media_path: str) -> Optional[str]:
        """Upload media to X and return media_id."""
        try:
            with open(media_path, "rb") as f:
                files = {"media": f}
                upload_response = self.oauth_session.post(
                    "https://upload.twitter.com/1.1/media/upload.json", files=files
                )

            if upload_response.status_code != 200:
                logger.error(
                    f"Failed to upload media. Status code: {upload_response.status_code}"
                )
                return None

            media_data = upload_response.json()
            return media_data.get("media_id_string")

        except Exception as e:
            logger.error(f"Media upload failed: {e}")
            return None

    def reset_counts(self):
        """Reset the post counter."""
        self.posts_count = 0
