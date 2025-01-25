<!-- ![Pippin, Autonomous Being Framework](media/pippin.jpg) -->
<img src="media/pippin.jpg" alt="Alt text" width="300" height="200" >

testing CI
# Pippin, The Digital Being Framework for Autonomous Agents

Welcome to Pippin — a flexible, open-source framework to create a digital “being” that:

- Learns about your goals/objectives and your character’s persona.
- Connects to various tools or APIs (via API keys or OAuth flows through Composio) to perform tasks.
- Dynamically creates and tests new “Activities” in pursuit of your objectives.
- Manages a memory system to track past actions and outcomes.
- Provides a web UI for easy onboarding/config, or a CLI wizard if you prefer terminal workflows.

---

## Table of Contents

1. **Overview**
2. **Features & Highlights**
3. **Prerequisites**
4. **Folder Structure**
5. **Quick Start**
    - Fork & Clone
    - Install Dependencies
    - Onboarding & Configuration
    - Launch the Agent
6. **Onboarding Flow: CLI vs. Web UI**
    - Core Steps (Same Under the Hood)
    - LLM Setup
    - Objectives & Character
    - Adding Skills via Composio or API Keys
    - Multiple LLM Model Support
7. **Default Activities**
8. **Using the Web UI**
    - Configuring Your Character & Constraints
    - Connecting Tools via OAuth (Composio)
    - Launching and Monitoring the Agent
9. **Using the CLI**
    - Re-running the Onboarding Wizard
    - Starting the Agent from Terminal
10. **Creating a New Skill for Solana-AgentKit (Manual Example)**
11. **Why Keep the AI/Web UI Default?**
12. **Extending & Creating Other Custom Activities**
13. **Memory, State & Activity Selection**
14. **Stopping or Pausing the Agent**
15. **Contributing**
16. **License**

---

## Overview

This project is designed to help you quickly spin up a self-improving, LLM-driven digital being that:

- Asks you for your objectives and character details.
- Integrates with tools to perform real-world tasks (e.g., tweeting, deploying tokens on Solana, generating images, or web scraping).
- Runs a continuous or scheduled loop, picking or creating new Activities to meet your goals.
- Stores logs in memory (short-term and long-term).
- Adapts by rewriting or generating Python code for new Activities on the fly!

You can choose to run everything from your terminal or via a web-based UI. Both flows do the same underlying initialization—so pick whichever is more comfortable.

---

## Features & Highlights

- **Flexible Onboarding:**
  - CLI Wizard or Web UI flow to gather essential info—no duplication of effort.
  - Prevents you from starting until you’ve provided at least one LLM API key (or local config) and a minimal character setup.

- **Multiple LLM Model Support:**
  - Provide one or more LLM API keys (OpenAI, GPT4All, or your custom provider).
  - Assign different models to tasks like code generation vs. daily analysis vs. activity selection.

- **Composio:**
  - OAuth-based gateway to 250+ tools (Twitter, Slack, Google, etc.).
  - Built-in flows for quickly adding new “skills” from connected apps.

- **Custom Skills:**
  - Easily add your own skill, e.g., solana-agent-kit, stable diffusion, or a Node.js microservice.
  - The default configuration can help you add manual API keys for tools not using Composio.

- **Default Activities:**
  - Activities for analyzing daily logs, brainstorming new Activities, generating .py files.

- **Configurable Constraints:**
  - E.g., “No more than 5 tweets per hour,” “Don’t create new tokens more than once a month.”

- **Memory System & State Tracking:**
  - The being “remembers” past actions, can reflect on them, and updates its own state (energy, mood, etc.).

---

## Prerequisites

- Python 3.9+ recommended.
- A GitHub account (to fork).
- A [Composio](https://composio.dev/) developer key (optional but recommended) if you want to do OAuth-based skill connections.

---

## Folder Structure

```
.
├─ activities/
│   ├─ activity_daily_thought.py
│   ├─ activity_suggest_new_activities.py
│   ├─ activity_build_or_update.py
│   └─ ... # More built-in or dynamically generated
├─ skills/
│   ├─ skill_lite_llm.py           # For local or remote LLM usage
│   ├─ skill_chat.py               # Example: OpenAI Chat
│   ├─ skill_solana_agent.py       # We'll create this manually (example)
│   ├─ skill_x_api.py              # For API skills
|   └─ skill_web_scraping.py       # Used for scraping information from the web
|
├─ framework/
│   ├─ main.py                     # Core DigitalBeing class, run loop
│   ├─ activity_selector.py        # Hybrid LLM + deterministic selection
│   ├─ memory.py                   # Short/long-term memory handling
│   ├─ state.py                    # Tracks energy, mood, etc.
│   ├─ shared_data.py              # Thread-safe data for cross-activity usage
│   └─ ...
├─ config/
│   ├─ character_config.json       # Where your being's name/personality go
│   ├─ activity_constraints.json   # Rate-limits, skill requirements, cooldowns
│   ├─ skills_config.json          # Enabled skills + required API keys
│   └─ ...
├─ server/
│   ├─ server.py                   # Web UI + WebSocket server
│   └─ static/                     # HTML/CSS/JS for the front-end
├─ tools/
│   └─ onboard.py                  # CLI-based onboarding wizard
├─ requirements.txt
├─ __init__.py
├─ server.py
└─ README.md                       # This document
```

---

## Quick Start

### 1. Fork & Clone

Fork this repo on GitHub.

Clone your fork:

```bash
git clone https://github.com/<your-username>/pippin-draft.git
cd pippin-draft
```

### 2. Install Dependencies (this step can be skipped if you use GitHub codespaces or the provided dev container)

First, install the UV package manager if not already installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then create and activate your virtual environment:
```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate  # On Unix/MacOS
# OR
.venv\Scripts\activate     # On Windows
```

Install the project dependencies:
```bash
uv pip install -r requirements.txt
```

### 3. Onboarding & Configuration

Navigate to the project directory:

```bash
cd my_digital_being
```

Copy the config_sample folder.
```bash
cp -r config_sample config
```

You can pick one of the following approaches:
- **CLI:** `python -m tools.onboard`
- **Web UI:** `python -m server` then open `http://localhost:8000` in your browser and follow the onboarding prompts.

Either way, you’ll be guided through:

1. Choosing your main LLM provider and providing at least one API key (or local model path).
2. Defining your character’s name, personality, objectives, constraints, etc.
3. Optionally connecting Composio or manually entering API keys for additional skills.
4. Ensuring at least one skill is fully configured so you can start the agent.

### 4. Launch the Agent

- **CLI:** `python -m framework.main`
- **Web UI:** Once onboarding is complete, a Start button appears—click to run the main loop.

---

# Onboarding Flow: CLI vs. Web UI

Both flows rely on shared logic that checks whether:

- You have a named character and objectives.
- At least one LLM skill is configured.
- (Optional) Composio or other skill credentials if you want advanced features.

If these conditions aren’t met, the agent cannot start. This ensures no half-configured usage.

---

## Core Steps (Same Under the Hood)

### LLM Setup

Choose one or more models. Examples:

- GPT4All for code generation
- GPT-3.5 for quick queries
- GPT-4 for reasoning

Provide the necessary API keys or local model paths. If using local GPT4All or other offline LLMs, the system can handle that, too.

### Objectives & Character

Specify:

- **Name:** e.g., “Optimus Mentis”
- **Personality:** e.g., “Helpful, curious, somewhat playful”
- **Objectives:** e.g., primary mission, secondary goals
- **Constraints:** e.g., “Do not create new tokens more than once a month”

(Stored in `character_config.json` and `activity_constraints.json`.)

### Adding Skills via Composio or API Keys

**Composio** is recommended if you want your being to do things like:

- Post on Twitter, Slack, or Gmail without manually handling each OAuth.
- Auto-fetch each app’s actions as “dynamic skills.”

API Keys are also possible for tools that either don’t integrate with Composio or if you prefer direct usage:

- `image_generation` skill with `OPENAI_API_KEY` or `STABLE_DIFFUSION_KEY`
- `solana_agent` skill with a private key environment variable

The onboarding flow will prompt for these keys. Provide or skip if optional.

### Multiple LLM Model Support

The system can handle multiple LLMs simultaneously, e.g.:

- **Activity Selector** => cheap GPT-3.5
- **Code Generation** => GPT-4
- **Daily Analysis** => local GPT4All

All you need is to enable the correct skill(s) in `skills_config.json` and optionally specify which model each feature uses. The default is to just pick one skill for everything.

---

## Default Activities

1. **AnalyzeDailyActivity**
   - Reads recent memory, calls your LLM-of-choice, logs a short reflection.

2. **SuggestNewActivities**
   - Brainstorms new tasks or expansions relevant to your objectives and constraints.

3. **BuildOrUpdateActivity**
   - Takes suggestions, calls an LLM to generate `.py` code, writes to `activities/`, reloads dynamically.

---

## Using the Web UI

### Configuring Your Character & Constraints

1. Under Onboarding or Configuration, fill in name, personality, objectives, constraints.
2. Click Save.

### Connecting Tools via OAuth (Composio)

1. In the Integrations or Skills tab, pick an app (e.g., Twitter).
2. Complete OAuth via Composio.
3. Confirm the status is “Connected.”

### Launching and Monitoring the Agent

- Once everything is set, click Start.
- Real-time logs show which Activity is chosen, memory usage, or new code generation.
- Pause or Stop anytime.

---

# Using the CLI

### Re-running the Onboarding Wizard

```bash
python my_digital_being/tools/onboard.py
```

(It will re-check your config, letting you update or skip certain steps.)

### Starting the Agent from Terminal

```bash
python -m framework.main
```

Logs appear in your console. Press `Ctrl+C` to stop.

---

## Creating a New Skill for Solana-AgentKit (Manual Example)

If you want your AI being to deploy tokens or interact with the Solana blockchain, you could rely on Composio (if supported) or manually add a skill that wraps Solana-AgentKit. Below is a minimal example that shows how to create a new skill in `skills/`, configure your key, and then reference it in an activity.

### 1. Skill Creation (`skill_solana_agent.py`)

In `skills/skill_solana_agent.py`, you might write:

```python
"""
Solana AgentKit Skill
This skill wraps solana-agent-kit for token deployment or other on-chain actions.
"""
import logging
import os
from typing import Optional
from framework.api_management import api_manager

logger = logging.getLogger(__name__)

class SolanaAgentSkill:
    def __init__(self):
        self.skill_name = "solana_agent"
        self.required_api_keys = ["SOLANA_PRIVATE_KEY"]
        # Register required keys with the system
        api_manager.register_required_keys(self.skill_name, self.required_api_keys)

        self.private_key: Optional[str] = None

    async def initialize(self) -> bool:
        """
        Fetch the SOLANA_PRIVATE_KEY from the secret storage (env or .env, etc.)
        Optionally test connectivity or run a minimal transaction if desired.
        """
        try:
            self.private_key = await api_manager.get_api_key(self.skill_name, "SOLANA_PRIVATE_KEY")
            if not self.private_key:
                logger.error("Solana private key not configured")
                return False

            # Here you could do a minimal validation or connection check if needed
            logger.info("SolanaAgentSkill initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing SolanaAgentSkill: {e}")
            return False

    async def deploy_token(self, name: str, symbol: str, supply: int, decimals: int = 9) -> dict:
        """
        Example method to deploy a new token using solana-agent-kit logic.
        """
        if not self.private_key:
            logger.error("Skill not initialized, missing private key")
            return {"success": False, "error": "Skill not initialized"}

        try:
            logger.info(f"Deploying token '{name}' on Solana with supply={supply}")
            # Pseudocode:
            # agent = SolanaAgentKit(self.private_key, "https://api.mainnet-beta.solana.com")
            # result = await agent.deployToken(name, "uri", symbol, decimals, supply)
            # return {"success": True, "mint": result["mint_address"]}

            # For demonstration, return a dummy result
            return {"success": True, "mint": "FakeMint123"}
        except Exception as e:
            logger.error(f"deploy_token error: {e}")
            return {"success": False, "error": str(e)}

# A global instance if you like
solana_agent_skill = SolanaAgentSkill()
```

Here’s what’s happening:

- `skill_name = "solana_agent"`.
- We call `api_manager.register_required_keys(...)` with `["SOLANA_PRIVATE_KEY"]`.
- `initialize()` loads the private key from secure storage.
- `deploy_token(...)` is an example method for real Solana logic—here it’s just a stub.

---

### 2. Register the Skill in `skills_config.json`

Open `config/skills_config.json` and add:

```json
{
  "solana_agent": {
    "enabled": true,
    "required_api_keys": ["SOLANA_PRIVATE_KEY"],
    "api_key_mapping": {
      "SOLANA_PRIVATE_KEY": "SOLANA_PRIVATE_KEY"
    }
  }
  // ... other skills ...
}
```

(Now the onboarding wizard or the web UI can prompt for `SOLANA_PRIVATE_KEY` if missing.)

---

### 3. Create or Update an Activity to Use the Skill

Next, we define an Activity that calls `solana_agent_skill.deploy_token(...)`. You can do this manually or let the AI produce code. Here’s a manual sample:

```python
# activities/activity_deploy_solana_token.py
import logging
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_solana_agent import solana_agent_skill

logger = logging.getLogger(__name__)

@activity(
    name="deploy_solana_token",
    energy_cost=1.0,
    cooldown=2592000,  # e.g. 30 days
    required_skills=["solana_agent"]
)
class DeploySolanaTokenActivity(ActivityBase):
    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting DeploySolanaTokenActivity...")

            # Initialize skill if not done already
            if not await solana_agent_skill.initialize():
                return ActivityResult(
                    success=False,
                    error="Failed to init Solana agent skill"
                )

            # Example config from shared data or state
            token_info = {
                "name": "My AI Token",
                "symbol": "AIT",
                "supply": 1000000,
                "decimals": 9
            }

            result = await solana_agent_skill.deploy_token(
                name=token_info["name"],
                symbol=token_info["symbol"],
                supply=token_info["supply"],
                decimals=token_info["decimals"]
            )

            if not result["success"]:
                return ActivityResult(
                    success=False,
                    error=result.get("error", "Unknown error from Solana skill")
                )

            logger.info(f"Token deployed with mint: {result['mint']}")
            return ActivityResult(
                success=True,
                data={"mint_address": result["mint"]}
            )

        except Exception as e:
            logger.error(f"Error in DeploySolanaTokenActivity: {e}")
            return ActivityResult(success=False, error=str(e))
```

---

### 4. Add Activity Constraints (Optional)

If you want to limit how often this token can be deployed, you can define constraints in `activity_constraints.json`. For instance:

```json
{
  "activity_cooldowns": {
    "DeploySolanaTokenActivity": 2592000
  },
  "activity_requirements": {
    "DeploySolanaTokenActivity": {
      "required_skills": ["solana_agent"]
    }
  }
}
```

(Now the system sees that `DeploySolanaTokenActivity` needs the `solana_agent` skill and has a 30-day cooldown.)

---
### 5. Restart or Reload

The system auto-reloads new Activities. If you just created `activity_deploy_solana_token.py`, you can either restart the agent or wait for the hot-reload if configured. Once running, the being might eventually choose this Activity if it meets constraints, or you can force it by removing cooldowns or making it your only viable option.

---

## Why Keep the AI/Web UI Default?

- **Ease of Use:** Our built-in “BuildOrUpdateActivity” can spontaneously propose new code, saving you from manual creation.
- **Web UI:** You can manually edit or refine the Python code from the interface.
- **Advanced Devs:** If you have specialized needs (like specific constraints or external libraries not well-suited to Composio), manual skill creation is perfect.

---

## Extending & Creating Other Custom Activities

- **Rely on the AI:** The being can spontaneously propose new `.py` code via `BuildOrUpdateActivity`. Approve or refine in the Web UI.
- **Manual:** Similar steps as above—create `activity_*.py`, define a class with the `@activity()` decorator, set constraints in `activity_constraints.json`.

Either way, once recognized, the new Activity is eligible for selection in the main loop.

---

## Memory, State & Activity Selection

### Memory
- **Short-term:** Recent logs or activity results (up to ~100).
- **Long-term:** Older logs archived by category.

### State
- Holds the being’s “energy,” “mood,” timestamps, or custom fields.

### ActivitySelector
- Filters out activities that fail cooldown/skill constraints.
- If multiple remain, calls an LLM to decide.
- If none remain, might propose new activities to fill a gap.

---

## Stopping or Pausing the Agent

- **Web UI:** Click Stop or Pause.
- **CLI:** Press `Ctrl+C`.

Memory/state persist, so you can resume next time.

---

## Contributing

We welcome PRs and feedback!

1. Fork this repo.
2. Create a feature branch for your changes.
3. Add/Improve code or docs.
4. Open a pull request—maintainers will review and merge.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file.

---

That’s it! We hope you enjoy building with the Pippin Framework. Whether you want your AI to brainstorm content, spin up tokens on Solana, or implement an entirely new skill from scratch, we’ve got you covered. If you have any questions or suggestions, please reach out or open an issue—happy hacking!
