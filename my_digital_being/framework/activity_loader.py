import importlib
import logging
import re
from pathlib import Path
from typing import Dict, Type, Any, Optional

logger = logging.getLogger(__name__)


def read_activity_code(activity_name: str) -> Optional[str]:
    """
    Reads the .py file from 'activities/' by the given filename (e.g. 'activity_tweet.py').
    Returns its text content or None if file not found.
    """
    activity_file = Path(__file__).parent.parent / "activities" / activity_name
    if not activity_file.exists():
        logger.warning(f"read_activity_code: File not found: {activity_file}")
        return None
    return activity_file.read_text()


def write_activity_code(activity_name: str, new_code: str) -> bool:
    """
    Writes 'new_code' into the .py file in 'activities/' with the given filename.
    Returns True on success, False on error.
    """
    activity_file = Path(__file__).parent.parent / "activities" / activity_name
    try:
        activity_file.write_text(new_code, encoding="utf-8")
        return True
    except Exception as e:
        logger.error(f"write_activity_code: Failed to write {activity_file}: {e}")
        return False


class ActivityLoader:
    def __init__(self, activities_path: str = None, config: dict = None):
        """
        :param activities_path: Where activity_*.py files live.
        :param config: The main config object from being.configs (used to skip disabled).
        """
        if activities_path is None:
            activities_path = Path(__file__).parent.parent / "activities"
        self.activities_path = Path(activities_path)

        # [ADDED] We'll read 'activities_config' from config
        self.activities_config = {}
        if config:
            self.activities_config = config.get("activity_constraints", {}).get(
                "activities_config", {}
            )

        self.loaded_activities: Dict[str, Type[Any]] = {}
        logger.info(f"ActivityLoader initialized with path: {self.activities_path}")

    def load_activities(self):
        """Load all activities from the activities directory."""
        if not self.activities_path.exists():
            logger.error(f"Activities directory not found: {self.activities_path}")
            return

        logger.info(f"Starting to load activities from: {self.activities_path}")
        for activity_file in self.activities_path.glob("activity_*.py"):
            try:
                logger.info(f"Found activity file: {activity_file}")
                file_text = activity_file.read_text()

                # We expect a pattern like: class SomeActivity(ActivityBase):
                class_match = re.search(
                    r"class\s+(\w+)\(.*ActivityBase.*\):", file_text
                )
                if not class_match:
                    logger.error(f"No recognized activity class in {activity_file}")
                    continue

                class_name = class_match.group(1)
                module_name = activity_file.stem  # e.g. "activity_draw"

                # Possibly skip if "enabled": false in activities_config
                activity_cfg = None
                if class_name in self.activities_config:
                    activity_cfg = self.activities_config[class_name]
                elif module_name in self.activities_config:
                    activity_cfg = self.activities_config[module_name]

                if activity_cfg and (activity_cfg.get("enabled") is False):
                    logger.info(
                        f"Activity {class_name} is disabled by config, skipping load."
                    )
                    continue

                spec = importlib.util.spec_from_file_location(
                    module_name, activity_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    activity_class = getattr(module, class_name)
                    self.loaded_activities[module_name] = activity_class
                    logger.info(
                        f"Successfully loaded activity {module_name} -> class {class_name}"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to load activity {activity_file}: {str(e)}", exc_info=True
                )

    def get_activity(self, activity_name: str) -> Optional[Type[Any]]:
        """Get an activity class by module name (e.g. 'activity_tweet')."""
        return self.loaded_activities.get(activity_name)

    def get_all_activities(self) -> Dict[str, Type[Any]]:
        """Get all loaded activities (module_name -> class)."""
        return self.loaded_activities.copy()

    def reload_activities(self):
        """Reload all activities by clearing and reloading."""
        self.loaded_activities.clear()
        self.load_activities()
