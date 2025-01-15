# activities/activity_evaluate.py

import logging
from typing import Dict, Any
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_chat import chat_skill

logger = logging.getLogger(__name__)


@activity(
    name="EvaluateActivity",
    energy_cost=0.3,
    cooldown=86400,  # example: 1 day
    required_skills=["openai_chat"],
)
class EvaluateActivity(ActivityBase):
    """
    Activity that attempts to 'simulate' how effective a newly generated activity might be
    or identify potential problems. This is purely an LLM-based guess, not guaranteed accurate.
    """

    def __init__(self):
        super().__init__()
        self.system_prompt = """You are an AI that evaluates the potential effectiveness
        of newly generated Activities. You consider whether the code is likely to run,
        fits the being's objectives, and avoids major pitfalls.
        Provide a short bullet-point analysis.
        """

    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting EvaluateActivity...")

            if not await chat_skill.initialize():
                return ActivityResult(
                    success=False, error="Failed to initialize openai_chat skill"
                )

            # Possibly fetch the last created/updated code from memory
            from framework.main import DigitalBeing

            being = DigitalBeing()
            being.initialize()
            recents = being.memory.get_recent_activities(limit=10)
            code_found = None

            for act in recents:
                if act["activity_type"] == "BuildOrUpdateActivity" and act.get(
                    "data", {}
                ):
                    data_content = act["data"]
                    if "code_snippet" in data_content:
                        code_found = data_content["code_snippet"]
                        break

            if not code_found:
                return ActivityResult(
                    success=False, error="No newly generated code found to evaluate"
                )

            prompt_text = (
                f"Here is the code for a newly created activity:\n{code_found}\n\n"
                "Evaluate how effective or risky this might be. Provide bullet points. "
                "Focus on alignment with objectives, potential errors, or improvements."
            )

            response = await chat_skill.get_chat_completion(
                prompt=prompt_text, system_prompt=self.system_prompt, max_tokens=250
            )
            if not response["success"]:
                return ActivityResult(success=False, error=response["error"])

            evaluation = response["data"]["content"]
            return ActivityResult(
                success=True,
                data={"evaluation": evaluation},
                metadata={
                    "model": response["data"]["model"],
                    "finish_reason": response["data"]["finish_reason"],
                },
            )

        except Exception as e:
            logger.error(f"Error in EvaluateActivity: {e}")
            return ActivityResult(success=False, error=str(e))
