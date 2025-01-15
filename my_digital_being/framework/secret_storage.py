"""Flexible secret storage system that works across different environments."""

import os
import logging
from typing import Optional, Dict, List
from abc import ABC, abstractmethod
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class SecretStorageBackend(ABC):
    """Abstract base class for secret storage backends."""

    @abstractmethod
    async def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret value by key."""
        pass

    @abstractmethod
    async def set_secret(self, key: str, value: str) -> bool:
        """Store a secret value."""
        pass

    @abstractmethod
    async def list_secrets(self) -> List[str]:
        """List all available secret keys."""
        pass


class EnvFileStorage(SecretStorageBackend):
    """Environment file-based secret storage."""

    def __init__(self, env_path: str = None):
        self.env_path = (
            Path(env_path) if env_path else Path(__file__).parent.parent / ".env"
        )
        load_dotenv(self.env_path)

    async def get_secret(self, key: str) -> Optional[str]:
        """Get secret from .env file."""
        return os.environ.get(key)

    async def set_secret(self, key: str, value: str) -> bool:
        """Set secret in .env file."""
        try:
            # Read existing contents
            env_content = {}
            if self.env_path.exists():
                with open(self.env_path, "r") as f:
                    for line in f:
                        if "=" in line and not line.startswith("#"):
                            k, v = line.strip().split("=", 1)
                            env_content[k] = v

            # Update or add new key
            env_content[key] = value

            # Write back to file
            with open(self.env_path, "w") as f:
                for k, v in env_content.items():
                    f.write(f"{k}={v}\n")

            # Update current environment
            os.environ[key] = value
            return True
        except Exception as e:
            logger.error(f"Error setting secret in .env file: {e}")
            return False

    async def list_secrets(self) -> List[str]:
        """List all secrets from .env file."""
        return [key for key in os.environ.keys() if key.endswith("_API_KEY")]


class ReplitSecretStorage(SecretStorageBackend):
    """Replit-specific secret storage implementation."""

    def __init__(self):
        """Initialize with EnvFileStorage as backup."""
        self.env_storage = EnvFileStorage()

    async def get_secret(self, key: str) -> Optional[str]:
        """Get secret from Replit's secure storage."""
        try:
            if "REPL_ID" in os.environ:
                from replit import db

                return db.get(key) or os.environ.get(key)
            return os.environ.get(key)
        except ImportError:
            logger.warning(
                "Replit module not available, falling back to environment variables"
            )
            return os.environ.get(key)
        except Exception as e:
            logger.error(f"Error getting secret from Replit storage: {e}")
            return os.environ.get(key)

    async def set_secret(self, key: str, value: str) -> bool:
        """Set secret using Replit's secure storage and backup to .env."""
        success = False
        try:
            if "REPL_ID" in os.environ:
                # Update environment variable immediately
                os.environ[key] = value

                # Store in Replit's db
                from replit import db

                db[key] = value
                success = True

            # Always try to update .env file as backup
            env_success = await self.env_storage.set_secret(key, value)
            return success or env_success

        except ImportError:
            logger.warning("Replit module not available, falling back to .env file")
            return await self.env_storage.set_secret(key, value)
        except Exception as e:
            logger.error(f"Error setting secret in Replit storage: {e}")
            return await self.env_storage.set_secret(key, value)

    async def list_secrets(self) -> List[str]:
        """List all secrets from both Replit and environment."""
        try:
            if "REPL_ID" in os.environ:
                from replit import db

                replit_keys = [key for key in db.keys() if key.endswith("_API_KEY")]
                env_keys = [
                    key for key in os.environ.keys() if key.endswith("_API_KEY")
                ]
                return list(set(replit_keys + env_keys))
            return [key for key in os.environ.keys() if key.endswith("_API_KEY")]
        except ImportError:
            return [key for key in os.environ.keys() if key.endswith("_API_KEY")]


class SecretManager:
    """Main interface for secret management."""

    def __init__(self):
        """Initialize with appropriate backend based on environment."""
        if "REPL_ID" in os.environ:
            self.backend = ReplitSecretStorage()
            logger.info("Using Replit secret storage backend")
        else:
            self.backend = EnvFileStorage()
            logger.info("Using .env file secret storage backend")

    async def get_api_key(self, skill_name: str, key_name: str) -> Optional[str]:
        """Get an API key for a specific skill."""
        env_key = f"{skill_name.upper()}_{key_name.upper()}_API_KEY"
        return await self.backend.get_secret(env_key)

    async def set_api_key(self, skill_name: str, key_name: str, value: str) -> bool:
        """Securely store an API key."""
        env_key = f"{skill_name.upper()}_{key_name.upper()}_API_KEY"
        success = await self.backend.set_secret(env_key, value)
        if success:
            # Also set any other skills that use the same key
            try:
                from framework.api_management import api_manager

                all_skills = api_manager.get_required_keys()
                for other_skill, required_keys in all_skills.items():
                    if key_name.upper() in [k.upper() for k in required_keys]:
                        other_env_key = (
                            f"{other_skill.upper()}_{key_name.upper()}_API_KEY"
                        )
                        await self.backend.set_secret(other_env_key, value)
            except Exception as e:
                logger.error(f"Error propagating API key to other skills: {e}")
        return success

    async def check_api_key_exists(self, skill_name: str, key_name: str) -> bool:
        """Check if an API key exists."""
        env_key = f"{skill_name.upper()}_{key_name.upper()}_API_KEY"
        return bool(await self.backend.get_secret(env_key))

    async def list_configured_keys(self) -> Dict[str, List[str]]:
        """Get all configured API keys grouped by skill."""
        secrets = await self.backend.list_secrets()
        configured_keys = {}

        for secret in secrets:
            if secret.endswith("_API_KEY"):
                parts = secret.split("_")
                if len(parts) >= 3:
                    skill_name = parts[0].lower()
                    key_name = "_".join(parts[1:-1]).lower()

                    if skill_name not in configured_keys:
                        configured_keys[skill_name] = []
                    configured_keys[skill_name].append(key_name)

        return configured_keys


# Global instance
secret_manager = SecretManager()
