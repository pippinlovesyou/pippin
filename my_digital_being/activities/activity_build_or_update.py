import logging
import re
from typing import Dict, Any
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from framework.activity_loader import write_activity_code
from skills.skill_chat import chat_skill

from framework.skill_config import DynamicComposioSkills
from framework.api_management import api_manager
from framework.main import DigitalBeing

logger = logging.getLogger(__name__)


@activity(
    name="BuildOrUpdateActivity",
    energy_cost=0.6,
    cooldown=172800,  # 2 days
    required_skills=["openai_chat"],
)
class BuildOrUpdateActivity(ActivityBase):
    """
    Activity that takes suggestions from memory, calls an LLM to generate or update
    Python activities, and writes them to the 'activities/' directory.

    We make two calls to the openai_chat skill:
      1) Get a short filename (activity_*.py).
      2) Generate the actual code snippet, referencing a sample template.

    The final code must:
      - Include `import logging` and any needed imports from `typing` or `framework`
      - Use the @activity decorator from `framework.activity_decorator`
      - Inherit from `ActivityBase`
      - Have an `async def execute(self, shared_data) -> ActivityResult:`
      - Possibly reference known manual-coded skills from `skills/skill_*.py` or
        dynamic Composio skills from `framework.api_management.api_manager` (if relevant).
    """

    def __init__(self):
        super().__init__()
        # Updated system prompt with additional guidelines from our experience
        self.system_prompt = (
            "You are an AI coder that converts user suggestions into valid Python activity files.\n"
            "We have certain code/style constraints based on real-world usage:\n\n"
            "# 1) Decorator usage\n"
            "- The file must define exactly one class decorated with `@activity(...)` from `framework.activity_decorator`.\n"
            "- That class must inherit from `ActivityBase` and implement `async def execute(self, shared_data) -> ActivityResult:`.\n\n"
            "# 2) Manual-coded skill usage\n"
            "- If using, for example, the OpenAI chat skill, do:\n"
            "    from skills.skill_chat import chat_skill\n"
            "    if not await chat_skill.initialize():\n"
            '        return ActivityResult.error_result("Chat skill not available")\n'
            '    response = await chat_skill.get_chat_completion(prompt="...")\n'
            "- DO NOT use self.get_skill_instance(...) or skill lookups in shared_data.\n"
            "- DO NOT define new skill constructors inline.\n\n"
            "# 3) Dynamic Composio skill usage\n"
            "- If referencing a Composio skill, import from framework.api_management:\n"
            "    from framework.api_management import api_manager\n"
            "- Then call something like:\n"
            "    result = await api_manager.composio_manager.execute_action(\n"
            "        action=\"TWITTER_TWEET_CREATE\",  # or e.g. 'Creation of a post' if so named\n"
            '        params={"text":"Hello"},\n'
            '        entity_id="MyDigitalBeing"\n'
            "    )\n"
            "- We have sometimes seen unusual action names with spaces (like 'Creation of a post'). That's okay.\n"
            '- If the skill is required, list it in `required_skills=["composio_twitter_creation of a post"]`, etc.\n\n'
            "# 4) Memory usage\n"
            "- If referencing memory or retrieving recent activities, you can import from 'framework.main' or 'framework.memory'.\n"
            "- Typically, do:\n"
            "     from framework.main import DigitalBeing\n"
            "     being = DigitalBeing()\n"
            "     being.initialize()\n"
            "     mem = being.memory.get_recent_activities(limit=10)\n"
            "- We do not store the skill or memory object in `shared_data` as a permanent reference. It's optional if you want.\n\n"
            "# 5) Common pitfalls\n"
            "- DO NOT reference unknown modules or placeholders like 'some_module'.\n"
            "- DO NOT rely on fallback calls to uninitialized XAPISkill, if you do not intend them.\n"
            "- If a dynamic skill name differs from your listing (like 'composio_twitter_twitter_tweet_create'), we might need EXACT naming.\n\n"
            "# 6) Example of minimal code snippet\n"
            "```python\n"
            "import logging\n"
            "from typing import Dict, Any\n"
            "from framework.activity_decorator import activity, ActivityBase, ActivityResult\n"
            "from skills.skill_chat import chat_skill\n"
            "from framework.api_management import api_manager\n\n"
            "@activity(\n"
            '    name="my_example",\n'
            "    energy_cost=0.5,\n"
            "    cooldown=3600,\n"
            '    required_skills=["openai_chat"]  # or dynamic composio skill name\n'
            ")\n"
            "class MyExampleActivity(ActivityBase):\n"
            '    """Short docstring explaining the activity"""\n'
            "    def __init__(self):\n"
            "        super().__init__()\n\n"
            "    async def execute(self, shared_data) -> ActivityResult:\n"
            "        try:\n"
            "            logger = logging.getLogger(__name__)\n"
            '            logger.info("Executing MyExampleActivity")\n\n'
            "            # e.g. using openai_chat:\n"
            "            if not await chat_skill.initialize():\n"
            '                return ActivityResult.error_result("Chat skill not available")\n'
            '            result = await chat_skill.get_chat_completion(prompt="Hello!")\n\n'
            "            # or dynamic composio skill, e.g.:\n"
            "            # result2 = await api_manager.composio_manager.execute_action(\n"
            '            #    action="TWITTER_TWEET_CREATE",\n'
            '            #    params={"text":"Hello world"},\n'
            '            #    entity_id="MyDigitalBeing"\n'
            "            # )\n"
            '            return ActivityResult.success_result({"message":"Done"})\n'
            "        except Exception as e:\n"
            "            return ActivityResult.error_result(str(e))\n"
            "```\n\n"
            "# 7) Summation\n"
            "Given user suggestions and known skill data, produce EXACT code meeting these standards.\n"
            "No triple backticks. Single @activity class only.\n"
        )

    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting BuildOrUpdateActivity...")

            # 1) Initialize chat skill
            if not await chat_skill.initialize():
                return ActivityResult(
                    success=False, error="Failed to initialize openai_chat skill"
                )

            # 2) Access the being + memory
            being = DigitalBeing()
            being.initialize()
            recent_activities = being.memory.get_recent_activities(limit=20)

            # 3) Gather skill info (both manual + dynamic)
            skills_config = being.configs.get("skills_config", {})
            manual_skill_list = []
            for skill_name, skill_info in skills_config.items():
                if isinstance(skill_info, dict):
                    desc = f"Skill: {skill_name}, enabled={skill_info.get('enabled')}"
                    req_keys = skill_info.get("required_api_keys", [])
                    desc += f", required_api_keys={req_keys}"
                    meta = skill_info.get("metadata", {})
                    if meta:
                        desc += f", metadata={meta}"
                    manual_skill_list.append(desc)

            dynamic_skills = DynamicComposioSkills.get_all_dynamic_skills()
            dynamic_skill_list = []
            for ds in dynamic_skills:
                d_name = ds["skill_name"]
                d_enabled = ds.get("enabled", True)
                d_req = ds.get("required_api_keys", [])
                d_meta = ds.get("metadata", {})
                desc = f"DynamicSkill: {d_name}, enabled={d_enabled}, required_api_keys={d_req}, metadata={d_meta}"
                dynamic_skill_list.append(desc)

            all_skills_block = "\n".join(manual_skill_list + dynamic_skill_list)
            if not all_skills_block.strip():
                all_skills_block = "(No known skills found)"

            # 4) Find last suggestions from memory (SuggestNewActivities)
            suggestion_texts = []
            for act in recent_activities:
                if act["activity_type"] == "SuggestNewActivities":
                    data_content = act.get("data", {})
                    if isinstance(data_content, dict) and "suggestions" in data_content:
                        suggestion_texts.append(data_content["suggestions"])

            if not suggestion_texts:
                return ActivityResult(
                    success=False,
                    error="No recent suggestions in memory; cannot build new activity",
                )
            combined_suggestions = "\n---\n".join(suggestion_texts)

            # ---------------------------------------------------------------------
            # A) FIRST LLM CALL - GET A SHORT FILENAME
            # ---------------------------------------------------------------------
            filename_prompt = (
                f"User Suggestions:\n{combined_suggestions}\n\n"
                f"Known Skills:\n{all_skills_block}\n\n"
                "Propose a short new file name that starts with 'activity_' and ends with '.py'. "
                "Do NOT provide any code, just the file name (no quotes, no backticks)."
            )

            filename_resp = await chat_skill.get_chat_completion(
                prompt=filename_prompt, system_prompt=self.system_prompt, max_tokens=50
            )
            if not filename_resp["success"]:
                return ActivityResult(success=False, error=filename_resp["error"])

            raw_filename = filename_resp["data"]["content"].strip()
            match_name = re.search(r"(activity_[\w-]+\.py)", raw_filename)
            if match_name:
                filename = match_name.group(1)
            else:
                filename = "activity_new_suggestion.py"

            # ---------------------------------------------------------------------
            # B) SECOND LLM CALL - GET THE FULL CODE
            # ---------------------------------------------------------------------
            code_prompt = (
                f"User Suggestions:\n{combined_suggestions}\n\n"
                f"Known Skills:\n{all_skills_block}\n\n"
                "Below is an example minimal template that shows how we want to reference manual-coded skills "
                "or dynamic composio skills:\n"
                "```python\n"
                "import logging\n"
                "from typing import Dict, Any\n"
                "from framework.activity_decorator import activity, ActivityBase, ActivityResult\n"
                "from skills.skill_chat import chat_skill\n"
                "from framework.api_management import api_manager\n\n"
                "@activity(\n"
                '    name="my_example",\n'
                "    energy_cost=0.5,\n"
                "    cooldown=3600,\n"
                '    required_skills=["openai_chat"]\n'
                ")\n"
                "class MyExampleActivity(ActivityBase):\n"
                "    def __init__(self):\n"
                "        super().__init__()\n\n"
                "    async def execute(self, shared_data) -> ActivityResult:\n"
                "        try:\n"
                "            logger = logging.getLogger(__name__)\n"
                '            logger.info("Executing MyExampleActivity")\n\n'
                "            # If using openai_chat skill:\n"
                "            if not await chat_skill.initialize():\n"
                '                return ActivityResult.error_result("Chat skill not available")\n'
                '            result = await chat_skill.get_chat_completion(prompt="Hello!")\n\n'
                "            # If using dynamic composio skill, e.g. 'composio_twitter_twitter_tweet_create':\n"
                "            #    result2 = await api_manager.composio_manager.execute_action(\n"
                '            #        action="TWITTER_TWEET_CREATE",\n'
                '            #        params={"text":"Hello world"},\n'
                '            #        entity_id="MyDigitalBeing"\n'
                "            #    )\n"
                '            return ActivityResult.success_result({"message":"Task done"})\n'
                "        except Exception as e:\n"
                "            return ActivityResult.error_result(str(e))\n"
                "```\n\n"
                f"Now produce a FULL Python file named {filename} with exactly one activity class that meets the instructions:\n"
                "- Single @activity decorator\n"
                "- Inherit from ActivityBase\n"
                "- Has `async def execute(...)`\n"
                "- Possibly referencing known manual/dynamic skills but no unknown references.\n"
                "- DO NOT wrap your code in triple backticks.\n"
            )

            code_resp = await chat_skill.get_chat_completion(
                prompt=code_prompt, system_prompt=self.system_prompt, max_tokens=1200
            )
            if not code_resp["success"]:
                return ActivityResult(success=False, error=code_resp["error"])

            code_snippet = code_resp["data"]["content"]
            code_snippet = self._clean_code_snippet(code_snippet)

            # ---------------------------------------------------------------------
            # Write to disk + Reload
            # ---------------------------------------------------------------------
            success = write_activity_code(filename, code_snippet)
            if not success:
                return ActivityResult(
                    success=False, error=f"Failed to write {filename} to disk"
                )

            # Reload so the new activity is recognized immediately
            being.activity_loader.reload_activities()

            return ActivityResult(
                success=True,
                data={"filename": filename, "code_snippet": code_snippet},
                metadata={"message": "Activity created/updated and reloaded"},
            )

        except Exception as e:
            logger.error(f"Error in BuildOrUpdateActivity: {e}", exc_info=True)
            return ActivityResult(success=False, error=str(e))

    def _clean_code_snippet(self, snippet: str) -> str:
        """
        Remove triple-backtick fences (` ```python ` or ` ``` `) from the snippet,
        plus any leading/trailing whitespace.
        """
        snippet = snippet.strip()
        # Remove any leading ```python or ```
        snippet = re.sub(r"^```(?:python)?", "", snippet, flags=re.IGNORECASE).strip()
        # Remove any trailing ```
        snippet = re.sub(r"```$", "", snippet).strip()
        return snippet
