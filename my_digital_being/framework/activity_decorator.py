import functools
import logging
from typing import Callable, Any, Dict, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


def activity(
    name: str,
    energy_cost: float = 0.2,
    cooldown: int = 0,
    required_skills: Optional[List[str]] = None,
):
    """Decorator for activity classes."""

    def decorator(cls):
        cls.activity_name = name
        cls.energy_cost = energy_cost
        cls.cooldown = cooldown
        cls.required_skills = required_skills or []
        cls.last_execution = None

        # Add metadata to the class
        cls.metadata = {
            "name": name,
            "energy_cost": energy_cost,
            "cooldown": cooldown,
            "required_skills": required_skills,
        }

        # Wrap the execute method
        original_execute = cls.execute

        @functools.wraps(original_execute)
        async def wrapped_execute(self, *args, **kwargs):
            try:
                # Pre-execution checks
                if not self._can_execute():
                    logger.warning(f"Activity {name} is on cooldown")
                    return ActivityResult(
                        success=False, error="Activity is on cooldown"
                    )

                # Log activity start
                logger.info(f"Starting activity: {name}")
                start_time = datetime.now()

                # Execute the activity
                result = await original_execute(self, *args, **kwargs)

                # Post-execution processing
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                cls.last_execution = end_time

                # Log activity completion
                logger.info(f"Completed activity: {name} in {duration:.2f} seconds")

                return result

            except Exception as e:
                logger.error(f"Error in activity {name}: {e}")
                return ActivityResult(success=False, error=str(e))

        cls.execute = wrapped_execute
        return cls

    return decorator


class ActivityResult:
    """Class to store activity execution results."""

    def __init__(
        self,
        success: bool,
        data: Optional[Any] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        data_dict = {}
        if self.data:
            if hasattr(self.data, "to_dict"):
                data_dict = self.data.to_dict()
            elif isinstance(self.data, dict):
                data_dict = self.data
            else:
                try:
                    data_dict = json.loads(json.dumps(self.data))
                except:
                    data_dict = str(self.data)

        return {
            "success": self.success,
            "data": data_dict,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def success_result(
        cls, data: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None
    ):
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def error_result(cls, error: str, metadata: Optional[Dict[str, Any]] = None):
        """Create an error result."""
        return cls(success=False, error=error, metadata=metadata)


class ActivityBase:
    """Base class for all activities."""

    def __init__(self):
        self.result = None
        self.last_execution: Optional[datetime] = None
        self.cooldown: int = 0

    def _can_execute(self) -> bool:
        """Check if the activity can be executed."""
        if self.last_execution is None:
            return True

        now = datetime.now()
        time_since_last = (now - self.last_execution).total_seconds()
        return time_since_last >= self.cooldown

    def get_result(self) -> Dict[str, Any]:
        """Get the result of the activity execution."""
        if isinstance(self.result, ActivityResult):
            return self.result.to_dict()
        return {
            "success": bool(self.result),
            "data": self.result if self.result else None,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }

    async def execute(self, shared_data) -> ActivityResult:
        """Base execute method that should be overridden by activities."""
        raise NotImplementedError("Activities must implement execute method")


def skill_required(skill_name: str):
    """Decorator to specify required skills for methods."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "required_skills"):
                self.required_skills = []
            if skill_name not in self.required_skills:
                self.required_skills.append(skill_name)
            return func(self, *args, **kwargs)

        return wrapper

    return decorator
