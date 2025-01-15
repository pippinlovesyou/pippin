"""Memory management system for storing and retrieving activity history."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Memory:
    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.short_term_memory: List[Dict[str, Any]] = []
        self.long_term_memory: Dict[str, Any] = {}
        self.memory_file = self.storage_path / "memory.json"
        self.initialize()

    def initialize(self):
        """Initialize memory system."""
        self._load_memory()

    def _load_memory(self):
        """Load memory from persistent storage."""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, "r") as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self.long_term_memory = data.get("long_term", {})
                            self.short_term_memory = data.get("short_term", [])
                        else:
                            logger.warning(
                                "Invalid memory file format, resetting memory"
                            )
                            self.long_term_memory = {}
                            self.short_term_memory = []
                            self.persist()  # Reset the file with proper format
                    except json.JSONDecodeError as je:
                        logger.error(f"Failed to parse memory file: {je}")
                        # Backup corrupted file
                        backup_path = self.memory_file.with_suffix(".json.bak")
                        self.memory_file.rename(backup_path)
                        logger.info(f"Backed up corrupted memory file to {backup_path}")
                        # Reset memory
                        self.long_term_memory = {}
                        self.short_term_memory = []
                        self.persist()  # Create new file with proper format
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            self.long_term_memory = {}
            self.short_term_memory = []

    def store_activity_result(self, activity_record: Dict[str, Any]):
        """Store the result of an activity in memory."""
        try:
            # Ensure we have a valid activity record
            if not isinstance(activity_record, dict):
                logger.error("Invalid activity record format")
                return

            # Extract and validate the result
            result = activity_record.get("result", {})
            if isinstance(result, dict):
                # Store standardized activity record with UTC timestamp
                memory_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "activity_type": activity_record.get("activity_type", "Unknown"),
                    "success": result.get("success", False),
                    "error": result.get("error"),
                    "data": result.get("data"),
                    "metadata": result.get("metadata", {}),
                }
                self.short_term_memory.append(memory_entry)
                self._consolidate_memory()
                self.persist()  # Persist after each update
                logger.info(
                    f"Stored activity result for {memory_entry['activity_type']}"
                )
            else:
                logger.error(f"Invalid result format in activity record: {result}")

        except Exception as e:
            logger.error(f"Failed to store activity result: {e}")

    def _consolidate_memory(self):
        """Consolidate short-term memory into long-term memory."""
        if len(self.short_term_memory) > 100:  # Keep last 100 activities in short-term
            older_memories = self.short_term_memory[
                :-50
            ]  # Move older ones to long-term
            self.short_term_memory = self.short_term_memory[-50:]

            for memory in older_memories:
                activity_type = memory["activity_type"]
                if activity_type not in self.long_term_memory:
                    self.long_term_memory[activity_type] = []
                self.long_term_memory[activity_type].append(memory)

    def get_recent_activities(
        self, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get recent activities from memory with success/failure status."""
        # Sort all activities by timestamp in descending order (most recent first)
        all_activities = sorted(
            self.short_term_memory, key=lambda x: x["timestamp"], reverse=True
        )

        # Apply pagination
        paginated_activities = all_activities[offset : offset + limit]

        # Format timestamps for display
        return [
            {
                "timestamp": self._format_timestamp(activity["timestamp"]),
                "activity_type": activity["activity_type"],
                "success": activity["success"],
                "error": activity.get("error"),
                "data": activity.get("data"),
                "metadata": activity.get("metadata", {}),
            }
            for activity in paginated_activities
        ]

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format ISO timestamp to human-readable format."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            return timestamp_str

    def get_activity_history(self, activity_type: str) -> List[Dict[str, Any]]:
        """Get history of specific activity type."""
        activities = self.long_term_memory.get(activity_type, [])
        return [
            {**activity, "timestamp": self._format_timestamp(activity["timestamp"])}
            for activity in activities
        ]

    def persist(self):
        """Persist memory to storage."""
        try:
            memory_data = {
                "short_term": self.short_term_memory,
                "long_term": self.long_term_memory,
            }

            # Write to a temporary file first
            temp_file = self.memory_file.with_suffix(".json.tmp")
            with open(temp_file, "w") as f:
                json.dump(memory_data, f, indent=2)

            # Rename temporary file to actual file (atomic operation)
            temp_file.replace(self.memory_file)

        except Exception as e:
            logger.error(f"Failed to persist memory: {e}")

    def clear(self):
        """Clear all memory."""
        self.short_term_memory = []
        self.long_term_memory = {}
        self.persist()

    def get_activity_count(self) -> int:
        """Get total number of activities in memory."""
        return len(self.short_term_memory) + sum(
            len(activities) for activities in self.long_term_memory.values()
        )

    def get_last_activity_timestamp(self) -> str:
        """Get formatted timestamp of the last activity."""
        if not self.short_term_memory:
            return "No activities recorded"

        last_activity = max(self.short_term_memory, key=lambda x: x["timestamp"])
        return self._format_timestamp(last_activity["timestamp"])
