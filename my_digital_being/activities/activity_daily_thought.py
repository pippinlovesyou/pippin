"""Activity for generating daily thoughts using OpenAI."""

import logging
from datetime import timedelta
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from framework.prompt_loader import PromptLoader
from skills.skill_chat import chat_skill

logger = logging.getLogger(__name__)


@activity(
    name="daily_thought",
    energy_cost=0.4,
    cooldown=1800,  # 30 minutes
    required_skills=["openai_chat"],
)
class DailyThoughtActivity(ActivityBase):
    """Generates insightful daily thoughts using OpenAI."""

    def __init__(self):
        super().__init__()
        self.prompt_loader = PromptLoader()
        
    async def execute(self, shared_data) -> ActivityResult:
        """Execute the daily thought activity."""
        try:
            logger.info("Starting daily thought generation")

            # Initialize required skills
            if not await chat_skill.initialize():
                return ActivityResult.error_result("Failed to initialize chat skill")

            # Load required prompts
            activity_name = self.__class__.__name__
            prompts = self.prompt_loader.get_prompts(activity_name)

            if not prompts:
                return ActivityResult.error_result("Failed to fetch prompts for {}".format(activity_name))

            prompt = prompts.get("prompt", "")
            system_prompt = prompts.get("system_prompt", "")

            # Generate the thought
            result = await chat_skill.get_chat_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=100,
            )

            if not result["success"]:
                return ActivityResult.error_result(result["error"])

            return ActivityResult.success_result(
                data={"thought": result["data"]["content"]},
                metadata={
                    "model": result["data"]["model"],
                    "finish_reason": result["data"]["finish_reason"],
                },
            )

        except Exception as e:
            logger.error(f"Error in daily thought activity: {e}")
            return ActivityResult.error_result(str(e))
