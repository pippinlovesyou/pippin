"""
LiteLLM Skill
Allows usage of multiple providers (Anthropic, OpenAI, OpenRouter, etc.) via litellm.
We read 'model_name' from skills_config["lite_llm"] if present,
and optionally fetch an API key from the secret manager for "LITELLM".
"""

import os
import logging
from typing import Optional, Dict, Any
from framework.api_management import api_manager
from framework.skill_config import SkillConfig

# litellm
from litellm import completion

logger = logging.getLogger(__name__)


class LiteLLMSkill:
    """Skill for chat/completion using LiteLLM."""

    def __init__(self):
        self.skill_name = "lite_llm"
        self.required_api_keys = ["LITELLM"]
        api_manager.register_required_keys(self.skill_name, self.required_api_keys)

        self.config = SkillConfig(self.skill_name)
        self.model_name: Optional[str] = None
        self._initialized = False

    async def initialize(self) -> bool:
        try:
            # Pull model_name from skill config
            self.model_name = self.config.get_config("model_name", "openai/gpt-4o")

            # Attempt to fetch the key from secret manager
            key = await api_manager.get_api_key(self.skill_name, "LITELLM")
            if key:
                os.environ["LITELLM_API_KEY"] = key
                logger.info("LiteLLM API key loaded from secret manager.")
            else:
                logger.info(
                    "No LITELLM API key found; assuming environment or no key needed."
                )

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LiteLLMSkill: {e}", exc_info=True)
            self._initialized = False
            return False

    async def get_chat_completion(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        max_tokens: int = 150,
    ) -> Dict[str, Any]:
        if not self._initialized:
            return {
                "success": False,
                "error": "LiteLLMSkill not initialized",
                "data": None,
            }

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = completion(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            choices = response.get("choices", [])
            if not choices:
                return {
                    "success": False,
                    "error": "No choices returned from LiteLLM",
                    "data": None,
                }

            content = choices[0]["message"]["content"]
            finish_reason = choices[0].get("finish_reason", "N/A")
            used_model = response.get("model", self.model_name)

            return {
                "success": True,
                "data": {
                    "content": content,
                    "finish_reason": finish_reason,
                    "model": used_model,
                },
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error in LiteLLMSkill completion: {e}", exc_info=True)
            return {"success": False, "error": f"LiteLLMSkill error: {e}", "data": None}


# Global instance
lite_llm_skill = LiteLLMSkill()
