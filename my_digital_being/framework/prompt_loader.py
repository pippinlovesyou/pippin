import json
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

class PromptLoader:
    def __init__(self, config_path: Optional[str] = None):
        """Load the prompts from a file once during initialization."""
        try:
            if config_path is None:
                config_path = Path(__file__).parent.parent / "config"
            else:
                config_path = Path(config_path)

            # Load the prompts from the file
            prompts_file_path = config_path / "prompts_config.json"
            with open(prompts_file_path, 'r', encoding="utf-8") as f:
                self.prompts_data = json.load(f)
                logger.info(f"PromptLoader initialized with config: {self.prompts_data}")

        except Exception as e:
            logger.error(f"Failed to load prompts from {config_path}: {e}")
            self.prompts_data = {}

    def get_prompts(self, activity_name: str):
        """Fetch the prompts for the specified activity name."""
        prompts = self.prompts_data.get(activity_name, {})
        if not prompts:
            logger.warning(f"No prompts found for activity: {activity_name}")
        return prompts