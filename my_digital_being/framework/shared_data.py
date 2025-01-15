import logging
from typing import Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


class SharedData:
    """Thread-safe shared data storage for activities and skills."""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._locks: Dict[str, Lock] = {}
        self._global_lock = Lock()

    def initialize(self):
        """Initialize shared data storage."""
        with self._global_lock:
            self._data = {"system": {}, "memory": {}, "state": {}, "temp": {}}
            for category in self._data:
                self._locks[category] = Lock()

    def get(self, category: str, key: str, default: Any = None) -> Any:
        """Get a value from shared data."""
        if category not in self._data:
            logger.warning(f"Attempting to access invalid category: {category}")
            return default

        with self._locks[category]:
            return self._data[category].get(key, default)

    def set(self, category: str, key: str, value: Any) -> bool:
        """Set a value in shared data."""
        if category not in self._data:
            logger.warning(f"Attempting to write to invalid category: {category}")
            return False

        with self._locks[category]:
            self._data[category][key] = value
        return True

    def update(self, category: str, updates: Dict[str, Any]) -> bool:
        """Update multiple values in a category."""
        if category not in self._data:
            logger.warning(f"Attempting to update invalid category: {category}")
            return False

        with self._locks[category]:
            self._data[category].update(updates)
        return True

    def delete(self, category: str, key: str) -> bool:
        """Delete a value from shared data."""
        if category not in self._data:
            logger.warning(f"Attempting to delete from invalid category: {category}")
            return False

        with self._locks[category]:
            if key in self._data[category]:
                del self._data[category][key]
                return True
        return False

    def clear_category(self, category: str) -> bool:
        """Clear all data in a category."""
        if category not in self._data:
            logger.warning(f"Attempting to clear invalid category: {category}")
            return False

        with self._locks[category]:
            self._data[category].clear()
        return True

    def get_category_data(self, category: str) -> Dict[str, Any]:
        """Get all data in a category."""
        if category not in self._data:
            logger.warning(f"Attempting to access invalid category: {category}")
            return {}

        with self._locks[category]:
            return self._data[category].copy()

    def exists(self, category: str, key: str) -> bool:
        """Check if a key exists in a category."""
        if category not in self._data:
            return False

        with self._locks[category]:
            return key in self._data[category]
