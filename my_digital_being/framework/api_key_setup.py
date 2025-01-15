"""Tool for securely setting up API keys."""

import logging
from typing import List, Dict, Tuple
import os
from .secret_storage import secret_manager

logger = logging.getLogger(__name__)


class APIKeySetup:
    """Manages the setup and validation of API keys for skills."""

    @staticmethod
    async def setup_keys(skill_name: str, required_keys: List[str]) -> Dict[str, bool]:
        """
        Set up API keys for a skill using the configured secret storage.

        Args:
            skill_name: Name of the skill requiring API keys
            required_keys: List of required API key names

        Returns:
            Dictionary mapping key names to setup success status
        """
        results = {}

        try:
            # For Replit environment, use ask_secrets
            if "REPL_ID" in os.environ:
                from replit import ask_secrets

                env_keys = [
                    f"{skill_name.upper()}_{key.upper()}_API_KEY"
                    for key in required_keys
                ]

                await ask_secrets(
                    secret_keys=env_keys,
                    user_message=f"""
The {skill_name} skill requires the following API keys to function:
{', '.join(required_keys)}

Please provide these keys to enable the skill's functionality.
These will be stored securely as environment variables.
""",
                )

            # Verify keys were set properly
            for key in required_keys:
                exists = await secret_manager.check_api_key_exists(skill_name, key)
                results[key] = exists

                if exists:
                    logger.info(f"Successfully set up {key} API key for {skill_name}")
                else:
                    logger.warning(f"Failed to set up {key} API key for {skill_name}")

        except Exception as e:
            logger.error(f"Error setting up API keys for {skill_name}: {e}")
            for key in required_keys:
                results[key] = False

        return results

    @staticmethod
    async def check_skill_keys(
        skill_name: str, required_keys: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if a skill has all required API keys configured.

        Args:
            skill_name: Name of the skill to test
            required_keys: List of required API keys

        Returns:
            Tuple of (success, list of missing keys)
        """
        missing_keys = []
        for key in required_keys:
            exists = await secret_manager.check_api_key_exists(skill_name, key)
            if not exists:
                missing_keys.append(key)

        return len(missing_keys) == 0, missing_keys

    @staticmethod
    async def list_skill_requirements(skill_requirements: Dict[str, List[str]]) -> str:
        """
        Get a formatted string of all skills and their API key requirements.

        Args:
            skill_requirements: Dictionary mapping skill names to their required keys

        Returns:
            Formatted string showing all skills and their required API keys
        """
        if not skill_requirements:
            return "No skills with API key requirements registered."

        output = ["Skill API Key Requirements:"]
        for skill, keys in skill_requirements.items():
            success, missing = await APIKeySetup.check_skill_keys(skill, keys)
            status = "✓" if success else "✗"
            output.append(f"\n{status} {skill}:")
            for key in keys:
                exists = await secret_manager.check_api_key_exists(skill, key)
                configured = "✓" if exists else "✗"
                output.append(f"  {configured} {key}")

        return "\n".join(output)
