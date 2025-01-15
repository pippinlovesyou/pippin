import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from framework.activity_decorator import activity, ActivityBase, ActivityResult
from framework.api_management import api_manager
from framework.memory import Memory
from skills.skill_chat import chat_skill

logger = logging.getLogger(__name__)


@activity(
    name="analyze_new_commits",
    energy_cost=0.4,
    cooldown=1000,  # e.g. 100 seconds for testing; update as needed (e.g. 86400 for daily)
    required_skills=["github_repo_commits"],
)
class AnalyzeNewCommitsActivity(ActivityBase):
    """
    Fetch recent commits from GitHub via Composio's GITHUB_LIST_COMMITS action.
    Filter to commits from the last 72 hours, skip any that were already analyzed,
    and then analyze them all in one chat prompt. Returns the analysis in ActivityResult.
    No manual calls to memory_obj.add_activity/store_activity - the system does that for us.
    """

    def __init__(self):
        super().__init__()
        self.composio_action = "GITHUB_LIST_COMMITS"
        self.github_owner = "yoheinakajima"  # example githubt username
        self.github_repo = "pippin"  # example repo
        self.github_branch = "main"
        self.lookback_hours = 144  # hours to look back

    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting AnalyzeNewCommitsActivity...")

            # 1) Initialize the chat skill
            if not await chat_skill.initialize():
                return ActivityResult(
                    success=False, error="Failed to initialize chat skill"
                )

            # 2) Retrieve memory reference and known commit SHAs (already analyzed)
            memory_obj = self._get_memory(shared_data)
            known_commit_shas = self._get_known_commit_shas(memory_obj)

            # 3) Fetch commits via Composio
            commits_response = self._list_commits_via_composio()
            if not commits_response["success"]:
                error_msg = commits_response.get("error", "Failed to fetch commits")
                return ActivityResult(success=False, error=error_msg)

            commits_data = commits_response.get("data", {}).get("details", [])
            if not commits_data:
                logger.info("No commits returned from GitHub (empty 'details').")
                return ActivityResult(
                    success=True, data={"message": "No commits found."}
                )

            # 4) Filter: only commits from the last X hours
            now_utc = datetime.utcnow()
            fresh_commits = []
            for c in commits_data:
                sha = c.get("sha")
                commit_date_str = (
                    c.get("commit", {}).get("author", {}).get("date")
                )  # e.g. 2025-01-07T08:16:00Z
                if not commit_date_str:
                    continue

                try:
                    commit_datetime = datetime.strptime(
                        commit_date_str, "%Y-%m-%dT%H:%M:%SZ"
                    )
                except ValueError:
                    logger.warning(f"Could not parse commit date: {commit_date_str}")
                    continue

                if (now_utc - commit_datetime) <= timedelta(hours=self.lookback_hours):
                    fresh_commits.append(c)
                else:
                    logger.info(
                        f"Skipping commit {sha} older than {self.lookback_hours} hours"
                    )

            if not fresh_commits:
                return ActivityResult(
                    success=True,
                    data={
                        "message": f"No commits in the last {self.lookback_hours} hours."
                    },
                )

            # 5) Determine which commits are new (not previously analyzed)
            new_commits = [
                c for c in fresh_commits if c.get("sha") not in known_commit_shas
            ]
            if not new_commits:
                logger.info("All recent commits were already analyzed.")
                return ActivityResult(
                    success=True, data={"message": "No new commits to analyze."}
                )

            # 6) Build a single chat prompt for all new commits
            prompt_text = self._build_batch_prompt(new_commits)
            logger.info(
                f"Sending one chat prompt with {len(new_commits)} new commits..."
            )

            chat_response = await chat_skill.get_chat_completion(
                prompt=prompt_text,
                system_prompt="You are a code review assistant. Summarize and analyze the following commits in detail.",
                max_tokens=500,  # Adjust as needed
            )
            if not chat_response["success"]:
                return ActivityResult(success=False, error=chat_response["error"])

            # 7) Get the combined analysis text from the chat skill
            combined_analysis = chat_response["data"]["content"].strip()

            # 8) Return success with the combined analysis
            # The activity loader or memory system will store the logs automatically.
            # We do not manually call memory_obj.add_activity or store_activity.
            return ActivityResult(
                success=True,
                data={
                    "analysis": combined_analysis,
                    "new_commit_count": len(new_commits),
                    "commits_analyzed": [c.get("sha") for c in new_commits],
                },
                metadata={
                    "model": chat_response["data"].get("model"),
                    "finish_reason": chat_response["data"].get("finish_reason"),
                    "prompt_used": prompt_text,
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze commits: {e}", exc_info=True)
            return ActivityResult(success=False, error=str(e))

    def _get_memory(self, shared_data) -> Memory:
        """
        Fetch or initialize memory object so we can read known commits from past activities.
        """
        system_data = shared_data.get_category_data("system")
        memory_obj: Memory = system_data.get("memory_ref")

        if not memory_obj:
            from framework.main import DigitalBeing

            being = DigitalBeing()
            being.initialize()
            memory_obj = being.memory

        return memory_obj

    def _get_known_commit_shas(self, memory_obj: Memory, limit: int = 50) -> List[str]:
        """
        Reads from memory which commits were already analyzed previously by this same activity.
        We'll skip re-analyzing them.
        """
        recent_activities = memory_obj.get_recent_activities(limit=limit, offset=0)
        known_shas = set()
        for act in recent_activities:
            # If we see "AnalyzeNewCommitsActivity" with success, parse its data
            if act.get("activity_type") == "AnalyzeNewCommitsActivity" and act.get(
                "success"
            ):
                # We rely on the final data posted in the ActivityResult
                # where "commits_analyzed" is a list of commit SHAs or something similar
                commits_analyzed = act.get("data", {}).get("commits_analyzed", [])
                for sha in commits_analyzed:
                    known_shas.add(sha)
        return list(known_shas)

    def _build_batch_prompt(self, commits: List[dict]) -> str:
        """
        Build a single prompt containing all new commits (sha + message).
        We'll ask the LLM to summarize them one by one, note improvements, etc.
        """
        lines = []
        for c in commits:
            sha = c.get("sha", "unknownSHA")[:7]
            message = c.get("commit", {}).get("message", "(no message)")
            lines.append(f"- SHA {sha}: {message}")

        joined_commits = "\n".join(lines)
        prompt = (
            f"Below is a list of {len(commits)} new commits:\n\n"
            f"{joined_commits}\n\n"
            f"Please provide a concise summary of each commit's changes, any improvements needed, "
            f"and note if there are any broader impacts across these commits. "
            f"Be thorough but concise."
        )
        return prompt

    def _list_commits_via_composio(self) -> Dict[str, Any]:
        """
        Calls Composio's GITHUB_LIST_COMMITS action.
        According to your logs, the relevant commits live under "data" -> "details".
        """
        try:
            from framework.composio_integration import composio_manager

            logger.info(
                f"Listing commits from owner='{self.github_owner}', repo='{self.github_repo}', "
                f"branch='{self.github_branch}' using action='{self.composio_action}'"
            )
            response = composio_manager._toolset.execute_action(
                action=self.composio_action,
                params={
                    "owner": self.github_owner,
                    "repo": self.github_repo,
                    "sha": self.github_branch,
                },
                entity_id="MyDigitalBeing",
            )

            # unify "successfull"/"successful"/"success" -> boolean
            success_val = response.get("success", response.get("successfull"))
            if success_val:
                return {"success": True, "data": response.get("data", {})}
            else:
                return {
                    "success": False,
                    "error": response.get(
                        "error", "Unknown or missing success key from Composio"
                    ),
                }

        except Exception as e:
            logger.error(f"Error listing commits from Composio: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
