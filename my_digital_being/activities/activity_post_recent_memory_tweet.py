import logging
from typing import Dict, Any, List
from urllib.parse import urlparse

from framework.activity_decorator import activity, ActivityBase, ActivityResult
from framework.api_management import api_manager
from framework.memory import Memory
from skills.skill_chat import chat_skill

logger = logging.getLogger(__name__)


@activity(
    name="post_recent_memories_tweet",
    energy_cost=0.4,
    cooldown=10000,  # e.g. ~2.7 hours for testing (adjust as needed)
    required_skills=["twitter_posting"],
)
class PostRecentMemoriesTweetActivity(ActivityBase):
    """
    Pulls recent memory items (up to N), ignoring certain activity types,
    filters out those used in the previous run of this activity,
    references personality + objectives from character_config,
    composes a short tweet via chat skill, and posts it.
    """

    def __init__(self, num_activities_to_fetch: int = 10):
        super().__init__()
        self.max_length = 280
        self.composio_action = "TWITTER_CREATION_OF_A_POST"
        self.twitter_username = "YourUserName"

        # Activity types to ignore in memory results
        self.ignored_activity_types = [
            "PostRecentMemoriesTweetActivity",  # ignore itself
            "PostTweetActivity",
        ]

        # How many recent memory entries to consider
        self.num_activities_to_fetch = num_activities_to_fetch

    async def execute(self, shared_data) -> ActivityResult:
        try:
            logger.info("Starting PostRecentMemoriesTweetActivity...")

            # 1) Initialize chat skill
            if not await chat_skill.initialize():
                return ActivityResult(
                    success=False, error="Failed to initialize chat skill"
                )

            # 2) Load personality + objectives from character config
            character_config = self._get_character_config(shared_data)
            personality_data = character_config.get("personality", {})
            objectives_data = character_config.get("objectives", {})
            # For example: objectives_data might be {"primary": "Spread positivity"}

            # 3) Fetch recent memories, ignoring certain activity types
            recent_memories = self._get_recent_memories(
                shared_data, limit=self.num_activities_to_fetch
            )
            if not recent_memories:
                logger.info("No relevant memories found to tweet about.")
                return ActivityResult(
                    success=True, data={"message": "No recent memories to share."}
                )

            # 4) Find which memories we used last time (to avoid repeats)
            used_memories_last_time = self._get_memories_used_last_time(shared_data)
            logger.info(f"Memories used last time: {used_memories_last_time}")

            # Filter out any overlap
            new_memories = [
                m for m in recent_memories if m not in used_memories_last_time
            ]

            # If all are duplicates, we skip tweeting
            if not new_memories:
                logger.info("All recent memories overlap with last time.")
                return ActivityResult(
                    success=True, data={"message": "No new memories to tweet."}
                )

            # 5) Build prompt referencing personality + objectives + the final set of memories
            prompt_text = self._build_chat_prompt(
                personality=personality_data,
                objectives=objectives_data,
                new_memories=new_memories,
            )

            # 6) Extract drawing URLs and upload to Twitter media
            drawing_urls = self._extract_drawing_urls(new_memories)
            media_ids = await self._upload_drawings_to_twitter(drawing_urls)
            
            # 7) Use chat skill to generate the tweet text
            chat_response = await chat_skill.get_chat_completion(
                prompt=prompt_text,
                system_prompt=(
                    "You are an AI that composes tweets with the given personality and objectives. "
                    "Tweet must be under 280 chars."
                ),
                max_tokens=200,
            )
            if not chat_response["success"]:
                return ActivityResult(success=False, error=chat_response["error"])

            tweet_text = chat_response["data"]["content"].strip()
            if len(tweet_text) > self.max_length:
                tweet_text = tweet_text[: self.max_length - 3] + "..."

            # 8) Post to Twitter via Composio
            post_result = self._post_tweet_via_composio(tweet_text, media_ids)
            if not post_result["success"]:
                error_msg = post_result.get(
                    "error", "Unknown error posting tweet via Composio"
                )
                logger.error(f"Tweet posting failed: {error_msg}")
                return ActivityResult(success=False, error=error_msg)

            tweet_id = post_result.get("tweet_id")
            tweet_link = (
                f"https://twitter.com/{self.twitter_username}/status/{tweet_id}"
                if tweet_id
                else None
            )

            # 9) Return success, storing the new memories in "data" so we can skip them next time
            logger.info(
                f"Successfully posted tweet about recent memories: {tweet_text[:50]}..."
            )
            return ActivityResult(
                success=True,
                data={
                    "tweet_id": tweet_id,
                    "content": tweet_text,
                    "recent_memories_used": new_memories,  # store these for next run
                },
                metadata={
                    "length": len(tweet_text),
                    "tweet_link": tweet_link,
                    "prompt_used": prompt_text,
                    "model": chat_response["data"].get("model"),
                    "finish_reason": chat_response["data"].get("finish_reason"),
                },
            )

        except Exception as e:
            logger.error(f"Failed to post recent memories tweet: {e}", exc_info=True)
            return ActivityResult(success=False, error=str(e))

    def _get_memories_used_last_time(self, shared_data) -> List[str]:
        """
        Look in memory for the most recent successful run of this same activity.
        Return the list of 'recent_memories_used' from that run, or [] if none.
        """
        system_data = shared_data.get_category_data("system")
        memory_obj: Memory = system_data.get("memory_ref")
        if not memory_obj:
            from framework.main import DigitalBeing

            being = DigitalBeing()
            being.initialize()
            memory_obj = being.memory

        # Search in the last ~10 runs for this activity
        recent_activities = memory_obj.get_recent_activities(limit=10, offset=0)
        for act in recent_activities:
            if act.get(
                "activity_type"
            ) == "PostRecentMemoriesTweetActivity" and act.get("success"):
                used = act.get("data", {}).get("recent_memories_used", [])
                if used:
                    return used
        return []

    def _get_character_config(self, shared_data) -> Dict[str, Any]:
        """
        Retrieve character_config from SharedData['system'] or re-init the Being if not found.
        """
        system_data = shared_data.get_category_data("system")
        maybe_config = system_data.get("character_config")
        if maybe_config:
            return maybe_config

        # fallback
        from framework.main import DigitalBeing

        being = DigitalBeing()
        being.initialize()
        return being.configs.get("character_config", {})

    def _get_recent_memories(self, shared_data, limit: int = 10) -> List[str]:
        """
        Pull up to 'limit' recent memory items (activities),
        ignoring certain activity types in self.ignored_activity_types.
        We'll just gather a short summary for each activity.
        """
        system_data = shared_data.get_category_data("system")
        memory_obj: Memory = system_data.get("memory_ref")

        if not memory_obj:
            from framework.main import DigitalBeing

            being = DigitalBeing()
            being.initialize()
            memory_obj = being.memory

        recent_activities = memory_obj.get_recent_activities(limit=50, offset=0)
        memories = []
        for act in recent_activities:
            act_type = act.get("activity_type")
            if act_type in self.ignored_activity_types:
                continue  # skip

            # Some minimal representation
            summary = f"{act_type} => {act.get('data', {})}"
            memories.append(summary)

            if len(memories) >= limit:
                break

        return memories

    def _build_chat_prompt(
        self,
        personality: Dict[str, Any],
        objectives: Dict[str, Any],
        new_memories: List[str],
    ) -> str:
        """
        Construct the user prompt: combine personality + objectives + the new memory summaries,
        and instruct the model to craft a short tweet.
        """
        # Personality lines
        trait_lines = [f"{t}: {v}" for t, v in personality.items()]
        personality_str = "\n".join(trait_lines)

        # Objectives lines
        objective_lines = []
        for k, v in objectives.items():
            objective_lines.append(f"{k}: {v}")
        objectives_str = (
            "\n".join(objective_lines)
            if objective_lines
            else "(No objectives specified)"
        )

        # Memories
        if new_memories:
            memories_str = "\n".join(f"- {txt}" for txt in new_memories)
        else:
            memories_str = "(No new memories)"

        prompt = (
            f"Our digital being has these personality traits:\n"
            f"{personality_str}\n\n"
            f"It also has these objectives:\n"
            f"{objectives_str}\n\n"
            f"Here are some new memories:\n"
            f"{memories_str}\n\n"
            f"Please craft a short tweet (under 280 chars) that references these memories, "
            f"reflects the personality and objectives, and ensures it's not repetitive or dull. "
            f"Keep it interesting, cohesive, and mindful of the overall tone.\n"
        )
        return prompt

    def _post_tweet_via_composio(self, tweet_text: str, media_ids: List[str]) -> Dict[str, Any]:
        """
        Post tweet via Composio with optional media_ids.
        """
        try:
            from framework.composio_integration import composio_manager

            logger.info(
                f"Posting tweet via Composio action='{self.composio_action}', text='{tweet_text[:50]}...', media_count={len(media_ids)}"
            )

            response = composio_manager._toolset.execute_action(
                action=self.composio_action,
                params={
                    "text": tweet_text, 
                    "media__media__ids": media_ids if media_ids else None
                },
                entity_id="MyDigitalBeing",
            )

            success_val = response.get("success", response.get("successfull"))
            if success_val:
                data_section = response.get("data", {})
                nested_data = data_section.get("data", {})
                tweet_id = nested_data.get("id")
                return {"success": True, "tweet_id": tweet_id}
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Unknown or missing success key"),
                }

        except Exception as e:
            logger.error(f"Error in Composio tweet post: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _extract_drawing_urls(self, memories: List[str]) -> List[str]:
        """
        Extract URLs from all DrawActivity entries in memories.
        Returns a list of valid URLs, empty list if none found.
        """
        drawing_urls = []
        
        for memory in memories:
            if memory.startswith("DrawActivity =>"):
                try:
                    # Extract the JSON-like string after '=>'
                    data_str = memory.split("=>")[1].strip()
                    # Convert string representation to dict
                    data = eval(data_str)
                    
                    # Extract URL from image_data
                    if 'image_data' in data and 'url' in data['image_data']:
                        url = data['image_data']['url']
                        # Validate URL
                        result = urlparse(url)
                        if all([result.scheme, result.netloc]):
                            drawing_urls.append(url)
                        else:
                            logger.warning(f"Invalid URL format found in DrawActivity: {url}")
                except Exception as e:
                    logger.error(f"Failed to extract drawing URL: {e}")
                    continue
        
        return drawing_urls

    async def _upload_drawings_to_twitter(self, drawing_urls: List[str]) -> List[str]:
        """
        Downloads images from URLs and uploads them to Twitter via Composio.
        Returns a list of Twitter media IDs.
        """
        import aiohttp
        import base64
        from framework.composio_integration import composio_manager
        
        media_ids = []
        
        if not drawing_urls:
            return media_ids
            
        async with aiohttp.ClientSession() as session:
            for url in drawing_urls:
                try:
                    # Download image
                    async with session.get(url) as response:
                        if response.status != 200:
                            logger.warning(f"Failed to download image from {url}: {response.status}")
                            continue
                            
                        image_data = await response.read()
                        
                    # Convert to base64
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    
                    # Extract filename from URL or use default
                    filename = url.split('/')[-1].split('?')[0] or 'image.png'
                    
                    # Upload to Twitter via Composio
                    upload_response = composio_manager._toolset.execute_action(
                        action="TWITTER_MEDIA_UPLOAD_MEDIA",
                        params={
                            "media": {
                                "name": filename,
                                "content": base64_image
                            }
                        },
                        entity_id="MyDigitalBeing"
                    )
                    
                    # Composio returns 'successfull' instead of 'successful'
                    if upload_response.get("successful") or upload_response.get("successfull"):
                        media_id = upload_response.get("media_id") or upload_response.get("data", {}).get("media_id")
                        if media_id:
                            media_ids.append(media_id)
                            logger.info(f"Successfully uploaded image to Twitter, media_id: {media_id}")
                        else:
                            logger.warning(f"Upload succeeded but no media_id returned. Response: {upload_response}")
                    else:
                        error = upload_response.get("error", "Unknown error")
                        logger.warning(f"Failed to upload image to Twitter: {error}")
                        
                except Exception as e:
                    logger.error(f"Error uploading image to Twitter: {e}", exc_info=True)
                    continue
                  
        logger.debug(f"Uploaded drawing URLs to Twitter media: {media_ids}")     
        return media_ids
