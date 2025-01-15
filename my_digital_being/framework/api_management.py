"""
Unified API key management system with flexible storage backends.
Implements:
 - get_skill_status -> returns any "required_keys"
 - get_composio_integrations -> calls composio_manager.list_available_integrations()
 - set_api_key -> if you want to store them
"""

import logging
from typing import Dict, Any, Optional, Set, List

from .secret_storage import secret_manager
from .composio_integration import composio_manager

logger = logging.getLogger(__name__)


class APIManager:
    def __init__(self):
        # Example: track required keys for each skill
        self._required_keys: Dict[str, Set[str]] = {}
        self._secret_manager = secret_manager
        self._composio_manager = composio_manager
        logger.info("Initialized API Manager with Composio integration")

    @property
    def composio_manager(self):
        return self._composio_manager

    def register_required_keys(self, skill_name: str, required_keys: List[str]) -> bool:
        """
        Register that a given skill_name requires the specified list of key names (e.g. ["OPENAI"]).
        """
        if not skill_name or not required_keys:
            return False
        self._required_keys[skill_name] = set(required_keys)
        logger.info(f"Registered keys for skill {skill_name}: {required_keys}")
        return True

    def get_required_keys(
        self, skill_name: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Return a dict of skill -> list of required keys.
        If skill_name is provided, return only that one skill's key list.
        """
        if skill_name:
            # Return just one skill's keys if it exists
            if skill_name in self._required_keys:
                return {skill_name: list(self._required_keys[skill_name])}
            else:
                return {skill_name: []}
        else:
            # Return all
            return {skill: list(keys) for skill, keys in self._required_keys.items()}

    async def check_api_key_exists(self, skill_name: str, key_name: str) -> bool:
        """
        Pass-through to secret_manager to check if a key is set.
        This is used in e.g. ImageGenerationSkill or other activities that do:
        `await api_manager.check_api_key_exists(...).`
        """
        return await self._secret_manager.check_api_key_exists(skill_name, key_name)

    async def get_api_key(self, skill_name: str, key_name: str) -> Optional[str]:
        """
        Return the actual API key string from secret_manager.
        Called by skill_chat.py's initialize() or skill_generate_image.py, etc.
        """
        return await self._secret_manager.get_api_key(skill_name, key_name)

    async def get_skill_status(self) -> Dict[str, Any]:
        """
        Example: For each skill, show which keys are configured or not.
        """
        skills_status = {}
        for skill, keys in self._required_keys.items():
            skill_info = {"display_name": skill.title(), "required_keys": {}}
            for k in keys:
                # Check if configured
                exists = await self._secret_manager.check_api_key_exists(skill, k)
                skill_info["required_keys"][k] = bool(exists)
            skills_status[skill] = skill_info
        return skills_status

    async def set_api_key(
        self, skill_name: str, key_name: str, value: str
    ) -> Dict[str, Any]:
        """
        Store a new API key into secret_manager for a given skill & key name.
        """
        success = await self._secret_manager.set_api_key(skill_name, key_name, value)
        return {"success": success, "affected_skills": {}}

    async def get_composio_integrations(self) -> List[Dict[str, Any]]:
        """
        Ask the ComposioManager for the available integrations (connected or not).
        """
        return await self._composio_manager.list_available_integrations()

    async def list_actions_for_app(self, app_name: str) -> Dict[str, Any]:
        """
        Calls composio_manager.list_actions_for_app(app_name).
        """
        return await self._composio_manager.list_actions_for_app(app_name)

    async def get_auth_schemes(self, app_name: str) -> Dict[str, Any]:
        """Get available authentication schemes for an app."""
        return await self._composio_manager.get_auth_schemes(app_name)

    async def initiate_api_key_connection(
        self, app_name: str, api_key: str
    ) -> Dict[str, Any]:
        """Initiate a connection using API key authentication."""
        return await self._composio_manager.initiate_api_key_connection(
            app_name, api_key
        )


# Global
api_manager = APIManager()
