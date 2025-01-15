import logging
from typing import Dict, Any
from framework.activity_decorator import activity, ActivityBase, ActivityResult

logger = logging.getLogger(__name__)


@activity(name="Test", energy_cost=0.2, cooldown=300, required_skills=[])
class TestActivity(ActivityBase):
    def __init__(self):
        super().__init__()

    async def execute(self, shared_data) -> ActivityResult:
        try:
            # Example: This is the main logic for "Test" activity
            logger.info("Executing Test activity")
            # TODO: Actual logic goes here
            return ActivityResult(success=True, data={"message": "Test done"})
        except Exception as e:
            logger.error(f"Error in Test activity: {e}")
            return ActivityResult(success=False, error=str(e))
