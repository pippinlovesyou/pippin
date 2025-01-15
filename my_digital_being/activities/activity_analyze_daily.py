# activities/activity_analyze_daily.py

import logging
from typing import Any
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from framework.memory import Memory
from skills.skill_chat import chat_skill

logger = logging.getLogger(__name__)


@activity(
    name="AnalyzeDailyActivity",
    energy_cost=0.3,
    cooldown=86400,  # 24 hours
    required_skills=["openai_chat"],
)
class AnalyzeDailyActivity(ActivityBase):
    """
    Activity that reviews the last day's logs from memory and produces a reflection
    or summary, storing that reflection in the memory system for future reference.
    """

    def __init__(self):
        super().__init__()
        self.system_prompt = """You are an AI that helps summarize the events, successes,
        or challenges from the digital being's recent memory. Keep the reflection concise and
        highlight any patterns or potential next steps."""

    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting daily analysis of memory...")

            # 1) Initialize the chat skill
            if not await chat_skill.initialize():
                return ActivityResult(
                    success=False, error="Failed to initialize openai_chat skill"
                )

            # 2) Retrieve the last ~10 memory entries for summarization
            memory_obj: Memory = shared_data.get(
                "system", "memory_ref"
            )  # or pass memory another way
            # If not found, fallback to your framework's global memory reference
            if not memory_obj:
                from framework.main import DigitalBeing

                # Fallback to the global being's memory if you prefer
                # In some setups, you can pass it in shared_data, or fetch it from a global reference
                being = DigitalBeing()
                being.initialize()
                memory_obj = being.memory

            recent_activities = memory_obj.get_recent_activities(limit=10, offset=0)

            # 3) Summarize them with the chat skill
            text_snippets = []
            for act in recent_activities:
                snippet = f"- {act['activity_type']}, success={act['success']}, data={act.get('data')}"
                text_snippets.append(snippet)

            combined_text = "\n".join(text_snippets)
            prompt = f"Here are recent logs:\n{combined_text}\n\nProduce a short daily reflection or summary."

            response = await chat_skill.get_chat_completion(
                prompt=prompt, system_prompt=self.system_prompt, max_tokens=150
            )
            if not response["success"]:
                return ActivityResult(success=False, error=response["error"])

            # 4) Return the reflection as success
            reflection = response["data"]["content"]
            return ActivityResult(
                success=True,
                data={"reflection": reflection},
                metadata={
                    "model": response["data"]["model"],
                    "finish_reason": response["data"]["finish_reason"],
                },
            )

        except Exception as e:
            logger.error(f"Error in AnalyzeDailyActivity: {e}")
            return ActivityResult(success=False, error=str(e))
