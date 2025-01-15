import logging
import random
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ActivitySelector:
    def __init__(self, constraints: Dict[str, Any], state):
        """
        :param constraints: A dictionary that typically includes:
            {
              "activity_cooldowns": { ... },  # No longer used
              "activity_requirements": { ... },
              "activities_config": { "DrawActivity": {"enabled": false}, ... }
            }
        :param state: The DigitalBeing's State object, used to check mood, energy, etc.
        """
        self.constraints = constraints
        self.state = state

        # Tracks the last time each activity class was executed
        self.last_activity_times: Dict[str, datetime] = {}

        # The loader is not set until set_activity_loader() is called
        self.activity_loader = None

    def set_activity_loader(self, loader):
        """
        Attach an ActivityLoader instance to this ActivitySelector.
        That loader has the loaded_activities dictionary (module_name -> activity_class).
        """
        self.activity_loader = loader
        logger.info("Activity loader set in selector")

    def select_next_activity(self):
        """
        Main entry point:
        1. Gather all available activities (not on cooldown, not disabled).
        2. Filter them by additional requirements like energy, skill requirements, etc.
        3. Use personality to pick one at random (weighted).
        4. Record the time we picked it.
        5. Return the activity instance or None.
        """
        if not self.activity_loader:
            logger.error("Activity loader not set; cannot select activity.")
            return None

        # Step 1: get all activities that are not on cooldown and are enabled
        available_activities = self._get_available_activities()
        if not available_activities:
            next_available = self.get_next_available_times()
            logger.info(
                f"No activities available at this time. Next available activities: {next_available}"
            )
            return None

        # Step 2: filter out ones that fail "energy" or "activity_requirements"
        suitable_activities = []
        for activity in available_activities:
            activity_name = activity.__class__.__name__
            if self._check_energy_requirements(
                activity
            ) and self._check_activity_requirements(activity_name):
                logger.info(f"Activity {activity_name} is suitable for execution.")
                suitable_activities.append(activity)
            else:
                logger.info(f"Activity {activity_name} does not meet requirements.")

        if not suitable_activities:
            logger.info("No activities suitable for current state.")
            return None

        # Step 3: personality-based selection
        # (If you have a "personality" dict in state, else use {}.)
        personality = self.state.get_current_state().get("personality", {})
        selected_activity = self._select_based_on_personality(
            suitable_activities, personality
        )

        if selected_activity:
            chosen_name = selected_activity.__class__.__name__
            logger.info(f"Selected activity: {chosen_name}")
            # Step 4: record the time we picked it
            self.last_activity_times[chosen_name] = datetime.now()

        return selected_activity

    def get_next_available_times(self) -> List[Dict[str, Any]]:
        """
        Provide info on when each loaded activity class will be available again.
        This is mostly for debugging/logging: "You can next run DrawActivity in 1.5 hours", etc.
        We now use the activity's decorator-based cooldown.
        """
        current_time = datetime.now()
        next_available = []

        all_activities = self.activity_loader.get_all_activities()

        for activity_name, activity_class in all_activities.items():
            base_name = activity_class.__name__

            # Pull cooldown from the class (decorator)
            cooldown = getattr(activity_class, "cooldown", 0)
            last_time = self.last_activity_times.get(base_name)

            if last_time:
                time_since_last = (current_time - last_time).total_seconds()
                time_remaining = max(0, cooldown - time_since_last)
                next_time = current_time + timedelta(seconds=time_remaining)

                next_available.append(
                    {
                        "activity": base_name,
                        "available_in_seconds": time_remaining,
                        "next_available_at": next_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "cooldown_period": cooldown,
                    }
                )
            else:
                # never run before => it's available now
                next_available.append(
                    {
                        "activity": base_name,
                        "available_in_seconds": 0,
                        "next_available_at": "Now",
                        "cooldown_period": cooldown,
                    }
                )

        # sort by soonest availability
        return sorted(next_available, key=lambda x: x["available_in_seconds"])

    def _get_available_activities(self) -> List[Any]:
        """
        Return a list of *activity instances* that:
          1) Are loaded by the ActivityLoader
          2) Are "enabled" in the config
          3) Are not on cooldown (based on the activity's own decorator-based cooldown)
        Then the caller can further filter them for energy or skill requirements.
        """
        available = []
        current_time = datetime.now()

        all_activities = self.activity_loader.get_all_activities()
        activities_config = self.constraints.get("activities_config", {})

        for module_name, activity_class in all_activities.items():
            base_name = activity_class.__name__

            # 1) skip if disabled
            if base_name in activities_config:
                if activities_config[base_name].get("enabled", True) is False:
                    logger.info(f"Skipping disabled activity: {base_name}")
                    continue

            # 2) check if it's on cooldown
            cooldown = getattr(activity_class, "cooldown", 0)
            last_time = self.last_activity_times.get(base_name)
            if last_time:
                time_since_last = (current_time - last_time).total_seconds()
                if time_since_last < cooldown:
                    logger.info(
                        f"{base_name} still on cooldown for {cooldown - time_since_last:.1f}s more."
                    )
                    continue

            # If we get here, the activity is enabled & not on cooldown
            try:
                instance = activity_class()
                logger.info(f"Created instance of {base_name} successfully.")
                available.append(instance)
            except Exception as e:
                logger.error(
                    f"Failed to create instance of {base_name}: {e}", exc_info=True
                )

        return available

    def _check_activity_requirements(self, activity_name: str) -> bool:
        """
        Check constraints['activity_requirements'][activity_name] if you need logic
        for required skills or memory usage. Currently returns True to accept all.
        """
        requirements = self.constraints.get("activity_requirements", {}).get(
            activity_name, {}
        )
        logger.debug(f"Checking requirements for {activity_name}: {requirements}")
        return True

    def _check_energy_requirements(self, activity) -> bool:
        """
        Check if the being has enough energy for the activity (activity.energy_cost).
        """
        current_energy = self.state.get_current_state().get("energy", 1.0)
        required_energy = getattr(activity, "energy_cost", 0.2)
        has_energy = current_energy >= required_energy

        if not has_energy:
            logger.info(
                f"Insufficient energy for {activity.__class__.__name__} "
                f"(required={required_energy}, current={current_energy})."
            )
        return has_energy

    def _select_based_on_personality(
        self, activities: List[Any], personality: Dict[str, float]
    ) -> Optional[Any]:
        """
        Given a list of candidate activity instances, choose one with a weighted random approach.
        """
        if not activities:
            return None

        weights = []
        for activity in activities:
            weight = 1.0
            if hasattr(activity, "creativity_factor"):
                weight *= (
                    1 + personality.get("creativity", 0.5) * activity.creativity_factor
                )
            if hasattr(activity, "social_factor"):
                weight *= (
                    1 + personality.get("friendliness", 0.5) * activity.social_factor
                )
            weights.append(weight)

        chosen = random.choices(activities, weights=weights, k=1)[0]
        return chosen
