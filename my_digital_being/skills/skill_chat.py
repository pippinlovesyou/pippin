"""OpenAI Chat Completion skill."""

import os
import logging
from typing import Optional, Dict, Any
from openai import OpenAI, APIError
from framework.api_management import api_manager

logger = logging.getLogger(__name__)


class ChatSkill:
    """Skill for chat completions using OpenAI's API."""

    def __init__(self):
        """Initialize the chat skill."""
        self.client: Optional[OpenAI] = None
        self.skill_name = "openai_chat"
        self.required_api_keys = ["openai"]
        # Register API key requirements
        api_manager.register_required_keys(self.skill_name, self.required_api_keys)

    async def initialize(self) -> bool:
        """Initialize the OpenAI client."""
        try:
            api_key = await api_manager.get_api_key(self.skill_name, "openai")
            if not api_key:
                logger.error("OpenAI API key not configured")
                return False

            self.client = OpenAI(api_key=api_key)
            # Test the API key with a minimal request
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=1,
            )
            return bool(response)
        except Exception as e:
            logger.error(f"Failed to initialize chat skill: {e}")
            return False

    async def get_chat_completion(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        max_tokens: int = 150,
    ) -> Dict[str, Any]:
        """
        Get a chat completion response.

        Args:
            prompt: The user's input prompt
            system_prompt: Optional system message to set the AI's behavior
            max_tokens: Maximum tokens in the response

        Returns:
            Dictionary containing success status, response data or error
        """
        if not self.client:
            return {
                "success": False,
                "error": "Chat skill not initialized",
                "data": None,
            }

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )

            return {
                "success": True,
                "data": {
                    "content": response.choices[0].message.content,
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                },
                "error": None,
            }

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return {"success": False, "error": str(e), "data": None}
        except Exception as e:
            logger.error(f"Unexpected error in chat completion: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "data": None,
            }


# Global instance
chat_skill = ChatSkill()
