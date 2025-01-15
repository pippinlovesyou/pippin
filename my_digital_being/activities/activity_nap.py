"""
Activity for taking a "nap" to simulate resting. 
We store a 'napping' state in shared_data, then return success.
"""

import logging
from typing import Dict, Any, List
from framework.activity_decorator import activity, ActivityBase, ActivityResult

logger = logging.getLogger(__name__)


@activity(
    name="nap",
    energy_cost=0,  # A nap might not cost energy, or you can set 0.2, etc.
    cooldown=1800,  # e.g. a 30-minute cooldown between naps
)
class NapActivity(ActivityBase):
    def __init__(self):
        super().__init__()
        self.nap_minutes = 15  # length of nap in minutes

    async def execute(self, shared_data) -> ActivityResult:
        """
        Execute the nap activity.
        We'll simulate a 'nap' by logging that we're napping,
        then store a record in shared_data that a nap took place.
        """
        try:
            logger.info(f"Taking a {self.nap_minutes}-minute nap.")
            # You can imagine "await asyncio.sleep(...)" if you wanted a real delay.

            # Store a record in shared_data:
            # e.g., shared_data.set('body_state', 'currently_napping', True)
            # or log the timestamp, etc.
            shared_data.set(
                "body_state",
                "nap_info",
                {"last_nap_duration": self.nap_minutes, "timestamp": "Just now!"},
            )

            logger.info("Nap finished. Feeling refreshed!")
            return ActivityResult(
                success=True,
                data={"nap_minutes": self.nap_minutes},
                metadata={
                    "message": "Nap complete",
                },
            )

        except Exception as e:
            logger.error(f"Nap failed: {e}")
            return ActivityResult(success=False, error=str(e))
