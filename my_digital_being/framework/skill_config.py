"""Secure skill configuration management system + dynamic Composio skills."""

import os
import logging
from typing import Dict, Any, Optional, Set, List

logger = logging.getLogger(__name__)


class SkillConfig:
    """Manages secure configuration for manually coded skills, including API keys."""

    # Class-level storage for tracking API key requirements
    _required_keys: Dict[str, Set[str]] = {}
    _initialized_skills: Set[str] = set()

    def __init__(self, skill_name: str):
        """Initialize skill configuration."""
        self.skill_name = skill_name
        self.config: Dict[str, Any] = {}
        self._load_config()

        if skill_name not in SkillConfig._initialized_skills:
            SkillConfig._initialized_skills.add(skill_name)

    def _load_config(self):
        """Load configuration from environment variables."""
        prefix = f"{self.skill_name.upper()}_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()
                self.config[config_key] = value

    def get_api_key(self, key_name: str) -> Optional[str]:
        """
        Safely retrieve an API key from environment variables.
        Raises ValueError if the key is required but not found.
        """
        env_key = f"{self.skill_name.upper()}_{key_name.upper()}_API_KEY"
        api_key = os.environ.get(env_key)

        if not api_key and self._is_key_required(key_name):
            error_msg = (
                f"Required API key '{key_name}' not found for skill '{self.skill_name}'"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        return api_key

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)

    def _is_key_required(self, key_name: str) -> bool:
        """Check if an API key is required for this skill."""
        return (
            self.skill_name in SkillConfig._required_keys
            and key_name in SkillConfig._required_keys[self.skill_name]
        )

    @classmethod
    def register_required_keys(cls, skill_name: str, required_keys: List[str]) -> bool:
        """Register required API keys for a manually-coded skill."""
        cls._required_keys[skill_name] = set(required_keys)
        missing_keys = []
        for key in required_keys:
            env_key = f"{skill_name.upper()}_{key.upper()}_API_KEY"
            if not os.environ.get(env_key):
                missing_keys.append(key)
        if missing_keys:
            logger.error(
                f"Missing required API keys for {skill_name}: {', '.join(missing_keys)}"
            )
            return False
        return True

    @classmethod
    def get_required_keys(cls, skill_name: str = None) -> Dict[str, Set[str]]:
        """Get all required API keys, optionally filtered by skill."""
        if skill_name:
            return {skill_name: cls._required_keys.get(skill_name, set())}
        return cls._required_keys.copy()

    @classmethod
    def verify_skill_keys(cls, skill_name: str) -> tuple[bool, list[str]]:
        """Verify that all required API keys for a skill are available."""
        if skill_name not in cls._required_keys:
            return True, []
        missing_keys = []
        for key in cls._required_keys[skill_name]:
            env_key = f"{skill_name.upper()}_{key.upper()}_API_KEY"
            if not os.environ.get(env_key):
                missing_keys.append(key)
        return len(missing_keys) == 0, missing_keys


#
# BELOW: Our new “DynamicComposioSkills” helper for storing discovered actions as if they were skills
#


class DynamicComposioSkills:
    """
    A registry for "dynamic" skill records discovered from Composio apps/actions.
    Each record might look like:
        {
          "skill_name": "composio_twitter_twitter_tweet_create",
          "enabled": True,
          "required_api_keys": ["COMPOSIO"],   # for example
          "metadata": {
             "composio_app": "TWITTER",
             "composio_action": "TWITTER_TWEET_CREATE"
          }
        }
    """

    # In-memory storage of these dynamic skills
    _dynamic_skills: List[Dict[str, Any]] = []

    @classmethod
    def register_composio_actions(cls, app_name: str, actions: List[str]):
        """
        For each action in `actions`, create a dynamic skill record and store it in _dynamic_skills.
        e.g. skill_name = "composio_{app_name}_{action_id}" (all lowercase)
        """
        for action_id in actions:
            skill_name = f"composio_{app_name.lower()}_{action_id.lower()}"
            skill_record = {
                "skill_name": skill_name,
                "enabled": True,
                # You could decide "required_api_keys": ["COMPOSIO"] or none at all
                "required_api_keys": ["COMPOSIO"],
                "metadata": {
                    "composio_app": app_name.upper(),
                    "composio_action": action_id,
                },
            }

            # Avoid duplicates if the user calls this multiple times
            if not any(s for s in cls._dynamic_skills if s["skill_name"] == skill_name):
                cls._dynamic_skills.append(skill_record)
                logger.info(f"[DynamicComposioSkills] Registered {skill_name}")

    @classmethod
    def get_all_dynamic_skills(cls) -> List[Dict[str, Any]]:
        """Return the entire list of dynamic Composio-based skill records."""
        return cls._dynamic_skills.copy()

    @classmethod
    def find_skill_by_name(cls, skill_name: str) -> Optional[Dict[str, Any]]:
        """Look up a single dynamic skill record by name."""
        for skill in cls._dynamic_skills:
            if skill["skill_name"] == skill_name:
                return skill
        return None
