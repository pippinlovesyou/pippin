import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from .memory import Memory
from .state import State
from .activity_selector import ActivitySelector
from .activity_loader import ActivityLoader
from .shared_data import SharedData
from .activity_decorator import ActivityResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DigitalBeing:
    def __init__(self, config_path: Optional[str] = None):
        # Use the config directory relative to this file's location
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config")
        self.config_path = Path(config_path)
        self.configs = self._load_configs()
        self.shared_data = SharedData()
        self.memory = Memory()
        self.state = State()
        self.activity_loader = ActivityLoader()
        self.activity_selector = ActivitySelector(
            self.configs.get("activity_constraints", {}), self.state
        )

    def _load_configs(self) -> Dict[str, Any]:
        """Load all configuration files."""
        configs = {}
        config_files = [
            "character_config.json",
            "activity_constraints.json",
            "skills_config.json",
        ]

        for config_file in config_files:
            try:
                with open(self.config_path / config_file, "r", encoding="utf-8") as f:
                    configs[config_file.replace(".json", "")] = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config {config_file}: {e}")
                configs[config_file.replace(".json", "")] = {}

        return configs

    def initialize(self):
        """Initialize the digital being."""
        logger.info("Initializing digital being...")

        # Load configurations
        self.configs = self._load_configs()
        logger.info("Configurations loaded")

        # Register API key requirements from skills_config
        skills_config = self.configs.get("skills_config", {})
        from framework.api_management import api_manager  # Avoid top-level import loops

        logger.info("Registering API key requirements for skills...")
        for skill_name, maybe_skill_dict in skills_config.items():
            # SKIP STR KEYS LIKE 'default_llm_skill'
            if not isinstance(maybe_skill_dict, dict):
                logger.debug(
                    f"Skipping non-dict skill config: {skill_name} -> {maybe_skill_dict}"
                )
                continue

            if maybe_skill_dict.get("enabled", False):
                required_keys = maybe_skill_dict.get("required_api_keys", [])
                if required_keys:
                    api_manager.register_required_keys(skill_name, required_keys)
                    logger.info(
                        f"Registered API key requirements for {skill_name}: {required_keys}"
                    )

        # Initialize sub-components
        self.memory.initialize()
        self.state.initialize(self.configs.get("character_config", {}))

        # Load activities
        self.activity_loader.load_activities()
        self.shared_data.initialize()

        # Set loader in selector
        self.activity_selector.set_activity_loader(self.activity_loader)

        logger.info("Digital being initialization complete")

    def is_configured(self) -> bool:
        """
        Check if being is 'configured'.
        We look at character_config for 'setup_complete': true
        """
        char_cfg = self.configs.get("character_config", {})
        return bool(char_cfg.get("setup_complete", False))

    async def run(self):
        """
        Main run loop. If not configured, we skip activity selection
        (but keep looping so the server can remain up).
        """
        logger.info("Starting digital being main loop...")

        try:
            while True:
                # If not configured, skip picking an activity
                if not self.is_configured():
                    logger.warning(
                        "Digital Being NOT configured. Skipping activity execution."
                    )
                    await asyncio.sleep(3)
                    continue

                current_activity = self.activity_selector.select_next_activity()
                if current_activity:
                    logger.info(
                        f"Selected activity: {current_activity.__class__.__name__}"
                    )
                    await self.execute_activity(current_activity)

                self.state.update()
                self.memory.persist()
                await asyncio.sleep(1)  # short delay to avoid busy-waiting

        except KeyboardInterrupt:
            logger.info("Shutting down digital being...")
            self.cleanup()

    async def execute_activity(self, activity) -> ActivityResult:
        """Execute a selected activity."""
        try:
            logger.info(
                f"Starting execution of activity: {activity.__class__.__name__}"
            )
            result = await activity.execute(self.shared_data)

            if not isinstance(result, ActivityResult):
                logger.warning(
                    f"Activity {activity.__class__.__name__} did not return an ActivityResult"
                )
                result = ActivityResult(
                    success=bool(result),
                    data=result if result else None,
                    error="Invalid result type" if not result else None,
                )

            # Store the activity result
            activity_record = {
                "timestamp": datetime.now().isoformat(),
                "activity_type": activity.__class__.__name__,
                "result": result.to_dict(),
            }
            self.memory.store_activity_result(activity_record)

            if result.success:
                logger.info(f"Successfully executed: {activity.__class__.__name__}")
                self.state.record_activity_completion()
            else:
                logger.warning(
                    f"Activity returned failure: {activity.__class__.__name__}"
                )

            return result

        except Exception as e:
            error_msg = f"Failed to execute {activity.__class__.__name__}: {e}"
            logger.error(error_msg)

            error_result = ActivityResult(success=False, error=str(e))
            self.memory.store_activity_result(
                {
                    "timestamp": datetime.now().isoformat(),
                    "activity_type": activity.__class__.__name__,
                    "result": error_result.to_dict(),
                }
            )

            return error_result

    def cleanup(self):
        """Cleanup resources before shutdown."""
        self.memory.persist()
        self.state.save()
        logger.info("Cleanup completed")


if __name__ == "__main__":
    import asyncio

    being = DigitalBeing()
    being.initialize()
    asyncio.run(being.run())
