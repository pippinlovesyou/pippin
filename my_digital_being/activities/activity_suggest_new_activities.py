# activities/activity_suggest_new_activities.py

import logging
from typing import Any, Dict
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_chat import chat_skill

# We import these so we can list out both manual + dynamic skill records
from framework.skill_config import DynamicComposioSkills
from framework.main import DigitalBeing

logger = logging.getLogger(__name__)


@activity(
    name="SuggestNewActivities",
    energy_cost=0.4,
    cooldown=259200,  # 3 days
    required_skills=["openai_chat"],
)
class SuggestNewActivities(ActivityBase):
    """
    Activity that examines the being's current objectives and constraints,
    then asks the LLM to propose new or modified Activities which may leverage
    any known skills (both manual-coded + dynamic from Composio).
    """

    def __init__(self):
        super().__init__()
        self.system_prompt = """You are an AI that helps brainstorm new or improved
Activities (Python-coded tasks) to achieve the being's goals, leveraging the skills
the system has available. The user will evaluate or build these later. Provide short,
actionable suggestions focusing on feasibility, alignment with constraints, and creativity.
If relevant, mention which skill(s) would be used for each suggestion.
        Do not plan on using API calls or making up URLs and rely on available skills for interacting with anything external to yourself."""

    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting new activity suggestion process...")

            # 1) Initialize the chat skill
            if not await chat_skill.initialize():
                return ActivityResult(
                    success=False, error="Failed to initialize openai_chat skill"
                )

            # 2) Gather the being + config
            being = DigitalBeing()
            being.initialize()
            char_cfg = being.configs.get("character_config", {})
            objectives = char_cfg.get("objectives", {})
            primary_obj = objectives.get("primary", "No primary objective found.")
            constraints_cfg = being.configs.get("activity_constraints", {})
            global_cons = constraints_cfg.get("global_constraints", "None specified")

            # 3) Gather all known skills (manual + dynamic)
            skills_config = being.configs.get("skills_config", {})

            # A. Manual-coded skills from skills_config.json
            manual_skill_list = []
            for skill_name, skill_info in skills_config.items():
                # skill_info can be dict or something else
                if isinstance(skill_info, dict):
                    # We'll build a short desc
                    desc = f"Skill: {skill_name}, enabled={skill_info.get('enabled')}"
                    # Add required keys, etc. if relevant
                    req_keys = skill_info.get("required_api_keys", [])
                    desc += f", required_api_keys={req_keys}"
                    meta = skill_info.get("metadata", {})
                    if meta:
                        desc += f", metadata={meta}"
                    manual_skill_list.append(desc)
                else:
                    # e.g. skip "default_llm_skill": "openai_chat"
                    pass

            # B. Dynamic (Composio) discovered skills
            dynamic_skills = DynamicComposioSkills.get_all_dynamic_skills()
            dynamic_skill_list = []
            for ds in dynamic_skills:
                d_name = ds["skill_name"]
                d_enabled = ds.get("enabled", True)
                d_req = ds.get("required_api_keys", [])
                d_meta = ds.get("metadata", {})
                desc = f"DynamicSkill: {d_name}, enabled={d_enabled}, required_api_keys={d_req}, metadata={d_meta}"
                dynamic_skill_list.append(desc)

            # 4) Combine skill descriptions into one block
            all_skills_block = "\n".join(manual_skill_list + dynamic_skill_list)
            if not all_skills_block.strip():
                all_skills_block = "(No known skills found)"

            # 5) Build final prompt
            prompt_text = (
                f"My primary objective: {primary_obj}\n"
                f"Global constraints or notes: {global_cons}\n\n"
                f"Known Skills:\n{all_skills_block}\n\n"
                f"Propose up to 3 new or modified Activities to help achieve my goal. "
                f"Highlight how each might use one or more of these skills (if relevant). "
                f"Keep suggestions short."
            )

            # 6) LLM call
            response = await chat_skill.get_chat_completion(
                prompt=prompt_text, system_prompt=self.system_prompt, max_tokens=300
            )
            if not response["success"]:
                return ActivityResult(success=False, error=response["error"])

            suggestions = response["data"]["content"]

            return ActivityResult(
                success=True,
                data={"suggestions": suggestions},
                metadata={
                    "model": response["data"]["model"],
                    "finish_reason": response["data"]["finish_reason"],
                },
            )

        except Exception as e:
            logger.error(f"Error in SuggestNewActivities: {e}")
            return ActivityResult(success=False, error=str(e))
