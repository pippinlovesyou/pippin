import json
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class State:
    def __init__(self, state_path: str = "./storage"):
        self.state_path = Path(state_path)
        self.state_path.mkdir(exist_ok=True)
        self.state_file = self.state_path / "state.json"
        self.current_state: Dict[str, Any] = {
            "mood": "neutral",
            "energy": 1.0,
            "last_activity_timestamp": None,
            "active_tasks": [],
            "personality": {},
        }

    def initialize(self, character_config: Dict[str, Any]):
        """Initialize state with character configuration."""
        self._load_state()
        self.current_state["personality"] = character_config.get("personality", {})
        self.save()

    def _load_state(self):
        """Load state from persistent storage."""
        try:
            if self.state_file.exists():
                with open(self.state_file, "r") as f:
                    self.current_state = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def update(self):
        """Update state based on current conditions."""
        current_time = datetime.now()

        # Update energy levels
        if self.current_state["last_activity_timestamp"]:
            last_activity = datetime.fromisoformat(
                self.current_state["last_activity_timestamp"]
            )
            time_diff = (current_time - last_activity).total_seconds()
            self.current_state["energy"] = min(
                1.0, self.current_state["energy"] + (time_diff / 3600) * 0.1
            )

        # Only update timestamp if there was a successful activity completion
        if hasattr(self, "_last_completed_activity"):
            self.current_state["last_activity_timestamp"] = current_time.isoformat()
            delattr(self, "_last_completed_activity")

        self.save()

    def get_current_state(self) -> Dict[str, Any]:
        """Get current state."""
        return self.current_state.copy()

    def update_mood(self, new_mood: str):
        """Update the current mood."""
        self.current_state["mood"] = new_mood
        self.save()

    def consume_energy(self, amount: float):
        """Consume energy for an activity."""
        self.current_state["energy"] = max(0.0, self.current_state["energy"] - amount)
        self.save()

    def record_activity_completion(self):
        """Mark that an activity was completed successfully."""
        self._last_completed_activity = True
        self.save()

    def add_active_task(self, task_id: str):
        """Add an active task."""
        if task_id not in self.current_state["active_tasks"]:
            self.current_state["active_tasks"].append(task_id)
            self.save()

    def remove_active_task(self, task_id: str):
        """Remove an active task."""
        if task_id in self.current_state["active_tasks"]:
            self.current_state["active_tasks"].remove(task_id)
            self.save()

    def save(self):
        """Save current state to persistent storage."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.current_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
