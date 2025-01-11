import json
import logging
import asyncio
from pathlib import Path

# We'll need to call api_manager in a synchronous context
from framework.api_management import api_manager
from framework.activity_loader import ActivityLoader

# Adjust these if your config is stored differently:
CHARACTER_CONFIG_FILE = Path(__file__).parent.parent / "config" / "character_config.json"
SKILLS_CONFIG_FILE = Path(__file__).parent.parent / "config" / "skills_config.json"
ACTIVITY_CONSTRAINTS_FILE = Path(__file__).parent.parent / "config" / "activity_constraints.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_json_config(path: Path) -> dict:
    """Helper to safely load JSON config from a file."""
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {path.name}: {e}")
        return {}

def save_json_config(path: Path, data: dict) -> None:
    """Helper to save JSON config atomically."""
    temp_file = path.with_suffix('.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        temp_file.replace(path)
    except Exception as e:
        logger.error(f"Failed to save {path.name}: {e}")

def prompt_user(prompt_text: str, default: str = None) -> str:
    """Prompt user for input with an optional default."""
    if default is not None:
        user_input = input(f"{prompt_text} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        return input(f"{prompt_text}: ").strip()

def prompt_yes_no(question: str, default: str = "yes") -> bool:
    """
    Prompt user for a yes/no answer with a default.
    Returns True if 'yes', False if 'no'.
    """
    yes_answers = ["yes", "y"]
    no_answers = ["no", "n"]

    if default.lower() in yes_answers:
        prompt_str = f"{question} [Y/n]: "
    else:
        prompt_str = f"{question} [y/N]: "

    while True:
        choice = input(prompt_str).strip().lower()
        if choice == "" and default:
            choice = default.lower()
        if choice in yes_answers:
            return True
        if choice in no_answers:
            return False
        print("Please respond with 'y' or 'n'.")


#
# Helper to set an API key synchronously by calling the async function
#
def set_api_key_sync(skill_name: str, key_name: str, value: str) -> bool:
    """Call api_manager.set_api_key(...) in a blocking manner for CLI convenience."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(api_manager.set_api_key(skill_name, key_name, value))
        loop.close()
        return bool(result.get("success", False))
    except Exception as e:
        logger.error(f"Error setting API key for {skill_name} -> {key_name}: {e}")
        return False

def configure_litellm(skills_config: dict) -> None:
    """
    Prompt user to configure a 'lite_llm' skill or skip.
    We allow a custom model_name (like 'anthropic/claude-3', 'openrouter/openai/gpt-4', etc.)
    If the user provides an API key, we store it via secret manager, not in skills_config.
    """
    print("\n--- LiteLLM Configuration ---")
    if prompt_yes_no("Would you like to configure LiteLLM (supports Anthropic, OpenAI, XAI, OpenRouter, etc.)?", "yes"):
        if "lite_llm" not in skills_config:
            skills_config["lite_llm"] = {
                "enabled": True,
                "required_api_keys": ["LITELLM"],  # We'll define "LITELLM" as the key name
                "api_key_mapping": {
                    "LITELLM": "LITELLM_API_KEY"
                },
                "model_name": None
            }
        else:
            # Ensure it's enabled
            skills_config["lite_llm"]["enabled"] = True
            rkeys = skills_config["lite_llm"].setdefault("required_api_keys", [])
            if "LITELLM" not in rkeys:
                rkeys.append("LITELLM")
            amap = skills_config["lite_llm"].setdefault("api_key_mapping", {})
            if "LITELLM" not in amap:
                amap["LITELLM"] = "LITELLM_API_KEY"

        model_name = prompt_user("Enter model name (e.g. 'anthropic/claude-3' or 'openrouter/openai/gpt-4')", "openai/gpt-4o")
        skills_config["lite_llm"]["model_name"] = model_name

        if prompt_yes_no("Do you want to provide an API key now?", "no"):
            the_key = prompt_user("Enter your LiteLLM-supported API key (or skip)", "")
            if the_key:
                success = set_api_key_sync("lite_llm", "LITELLM", the_key)
                if success:
                    print("LiteLLM API key stored securely!")
                else:
                    print("Failed to store LiteLLM API key. Check logs.")

        use_as_default = prompt_yes_no("Use this lite_llm skill as your default LLM for code generation?", "yes")
        if use_as_default:
            skills_config["default_llm_skill"] = "lite_llm"
    else:
        print("Skipping LiteLLM setup. You can still configure another LLM skill or skip LLM altogether.")

def configure_openai_chat(skills_config: dict) -> None:
    """
    Prompt user to configure openai_chat skill (like GPT).
    If the user provides an API key, we store it in secret manager, not in skills_config.
    """
    print("\n--- OpenAI Chat Configuration ---")
    if "openai_chat" not in skills_config:
        skills_config["openai_chat"] = {
            "enabled": True,
            "required_api_keys": ["OPENAI"],
            "api_key_mapping": {"OPENAI": "OPENAI_API_KEY"}
        }
    else:
        skills_config["openai_chat"]["enabled"] = True

    openai_key = prompt_user("Enter your OPENAI_API_KEY (leave blank if stored in .env or skipping)", "")
    if openai_key:
        success = set_api_key_sync("openai_chat", "OPENAI", openai_key)
        if success:
            print("OpenAI API key stored securely!")
        else:
            print("Failed to store OpenAI key. Check logs.")

    if prompt_yes_no("Use openai_chat as the default LLM skill for code generation?", "no"):
        skills_config["default_llm_skill"] = "openai_chat"

def configure_primary_llm(skills_config: dict) -> None:
    """
    Let user pick from:
    1) LiteLLM skill
    2) OpenAI Chat skill
    3) No LLM
    """
    print("\n--- Primary LLM Choice ---")
    print("1) LiteLLM (anthropic, openai, openrouter, etc.)")
    print("2) OpenAI Chat skill only")
    print("3) None / Skip LLM entirely")

    choice = prompt_user("Enter 1, 2, or 3", default="1")
    if choice == "1":
        configure_litellm(skills_config)
    elif choice == "2":
        configure_openai_chat(skills_config)
    else:
        print("Skipping LLM entirely. No GPT-based code generation or advanced tasks.")
        if "default_llm_skill" in skills_config:
            del skills_config["default_llm_skill"]

def configure_character_basics(character_config: dict) -> None:
    print("\n--- Character Basic Setup ---")
    current_name = character_config.get("name", "Digital Being")
    new_name = prompt_user("Character Name", default=current_name)
    character_config["name"] = new_name

    current_objective = character_config.get("objectives", {}).get("primary", "Assist users")
    new_objective = prompt_user("Primary Objective", default=current_objective)

    if "objectives" not in character_config:
        character_config["objectives"] = {}
    character_config["objectives"]["primary"] = new_objective

def configure_advanced_text(character_config: dict, activity_constraints: dict) -> None:
    if prompt_yes_no("Would you like to define advanced objective text / constraints / examples?", "no"):
        print("\n--- Advanced Objectives ---")
        lines = []
        first_line = prompt_user("Enter multi-line advanced objectives. Press Enter on blank line to finish:", "")
        if first_line.strip():
            lines.append(first_line)
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        combined = "\n".join(lines)
        if combined:
            character_config.setdefault("objectives", {})
            character_config["objectives"]["advanced"] = combined

        print("\n--- Example Activities ---")
        lines2 = []
        first_line = prompt_user("Enter multi-line example activities. Press Enter on blank line to finish:", "")
        if first_line.strip():
            lines2.append(first_line)
        while True:
            line = input()
            if not line.strip():
                break
            lines2.append(line)
        combined2 = "\n".join(lines2)
        if combined2:
            character_config["example_activities"] = combined2

        print("\n--- General Constraints ---")
        lines3 = []
        first_line = prompt_user("Enter multi-line constraints. Press Enter on blank line to finish:", "")
        if first_line.strip():
            lines3.append(first_line)
        while True:
            line = input()
            if not line.strip():
                break
            lines3.append(line)
        combined3 = "\n".join(lines3)
        if combined3:
            activity_constraints["global_constraints"] = combined3

def configure_other_skills(skills_config: dict) -> None:
    print("\n--- Additional Skills ---")
    skill_names = sorted(skills_config.keys())
    for skill_name in skill_names:
        if skill_name in ["openai_chat", "lite_llm", "default_llm_skill"]:
            continue
        skill_data = skills_config[skill_name]
        is_enabled = skill_data.get("enabled", False)
        user_enable = prompt_yes_no(f"Enable skill '{skill_name}'?", "yes" if is_enabled else "no")
        skill_data["enabled"] = user_enable

        if user_enable and skill_data.get("required_api_keys"):
            for required_key in skill_data["required_api_keys"]:
                env_key = skill_data.get("api_key_mapping", {}).get(required_key, f"{skill_name.upper()}_{required_key}")
                val = prompt_user(f"Enter value for {env_key} (leave blank to skip)", "")
                if val:
                    success = set_api_key_sync(skill_name, required_key, val)
                    if success:
                        print(f"API key for {skill_name}:{required_key} stored!")
                    else:
                        print(f"Failed to store API key for {skill_name}:{required_key}")

# [ADDED] Let user pick which activities to enable/disable (CLI approach)
def configure_activities_cli(activities_config: dict) -> None:
    """
    We discover the available activity classes from the ActivityLoader and let the user
    choose which to enable. We store "enabled": bool in the final JSON under activities_config.
    """
    print("\n--- Activity Enable/Disable Setup (CLI) ---")
    loader = ActivityLoader()
    loader.load_activities()
    found_activities = loader.get_all_activities()  # e.g. {"activity_draw": DrawActivity, ...}

    for mod_name, cls in found_activities.items():
        class_name = cls.__name__  # e.g. "DrawActivity"
        # If we already have an entry, use it; otherwise default to True
        current_enabled = activities_config.get(class_name, {}).get("enabled", True)
        user_enable = prompt_yes_no(f"Enable activity '{class_name}'?", "yes" if current_enabled else "no")

        if class_name not in activities_config:
            activities_config[class_name] = {}
        activities_config[class_name]["enabled"] = user_enable


def main():
    print("=========================================================")
    print(" Welcome to the Autonomous Being CLI Onboarding")
    print("=========================================================")

    character_config_path = CHARACTER_CONFIG_FILE
    skills_config_path = SKILLS_CONFIG_FILE
    activity_constraints_path = ACTIVITY_CONSTRAINTS_FILE

    character_config = load_json_config(character_config_path)
    skills_config = load_json_config(skills_config_path)
    activity_constraints = load_json_config(activity_constraints_path)

    # 1) Primary LLM choice
    configure_primary_llm(skills_config)

    # 2) Basic character config
    configure_character_basics(character_config)

    # 3) Advanced text (objectives, examples, constraints)
    configure_advanced_text(character_config, activity_constraints)

    # 4) Other skills
    configure_other_skills(skills_config)

    # [ADDED] 5) Let user pick which activities to enable/disable in CLI
    # If you prefer to do this only in front-end, you can skip this step or remove it.
    if "activities_config" not in activity_constraints:
        activity_constraints["activities_config"] = {}
    configure_activities_cli(activity_constraints["activities_config"])

    # Set setup_complete to true
    character_config["setup_complete"] = True

    # Save updated (without storing any user-provided API keys in JSON)
    print("\nSaving updated JSON configs...")
    save_json_config(character_config_path, character_config)
    save_json_config(skills_config_path, skills_config)
    save_json_config(activity_constraints_path, activity_constraints)

    print("\nOnboarding complete!")
    print("You may now run 'python -m framework.main' or 'python -m server.server' to launch the AI being.")
    print("-----------------------------------------------------------")


if __name__ == "__main__":
    main()
