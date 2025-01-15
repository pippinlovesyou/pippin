"""Drawing activity implementation."""

import logging
from typing import Dict, Any
from framework.activity_decorator import activity, ActivityBase, ActivityResult
from skills.skill_generate_image import ImageGenerationSkill
from framework.api_management import api_manager

logger = logging.getLogger(__name__)


@activity(
    name="draw",
    energy_cost=0.6,
    cooldown=7200,  # 2 hours
    required_skills=["image_generation"],
)
class DrawActivity(ActivityBase):
    def __init__(self):
        super().__init__()
        self.default_size = (512, 512)
        self.default_format = "png"

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the drawing activity."""
        try:
            logger.info("Starting drawing activity")

            # Initialize the image generation skill with configuration
            image_skill = ImageGenerationSkill(
                {
                    "enabled": True,
                    "max_generations_per_day": 50,
                    "supported_formats": ["png", "jpg"],
                }
            )

            # Verify the skill can generate images
            if not await image_skill.can_generate():
                error_msg = "Image generation is not available at this time"
                logger.error(error_msg)
                return ActivityResult(success=False, error=error_msg)

            # Generate drawing prompt
            prompt = self._generate_prompt(shared_data)

            # Generate the image
            result = await image_skill.generate_image(
                prompt=prompt, size=self.default_size, format=self.default_format
            )

            if result.get("success"):
                # Store the generated image data
                shared_data.set(
                    "memory",
                    f"drawing_{result['image_data']['generation_id']}",
                    {"prompt": prompt, "image_data": result["image_data"]},
                )

                logger.info(f"Successfully generated image for prompt: {prompt}")
                return ActivityResult(
                    success=True,
                    data={
                        "generation_id": result["image_data"]["generation_id"],
                        "prompt": prompt,
                        "image_data": result["image_data"],
                    },
                    metadata={"size": self.default_size, "format": self.default_format},
                )
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Failed to generate image: {error_msg}")
                return ActivityResult(success=False, error=error_msg)

        except Exception as e:
            logger.error(f"Failed to generate drawing: {e}")
            return ActivityResult(success=False, error=str(e))

    def _generate_prompt(self, shared_data) -> str:
        """Generate a drawing prompt based on current state and memory."""
        state = shared_data.get("state", "current_state", {})
        personality = state.get("personality", {})
        mood = state.get("mood", "neutral")

        # Base prompts for different moods
        mood_prompts = {
            "happy": "a sunny landscape with vibrant colors",
            "neutral": "a peaceful scene with balanced composition",
            "sad": "a rainy day with muted colors",
        }

        # Get base prompt from mood
        base_prompt = mood_prompts.get(mood, mood_prompts["neutral"])

        # Modify based on personality
        if personality.get("creativity", 0) > 0.7:
            base_prompt += " with surreal elements"
        if personality.get("curiosity", 0) > 0.7:
            base_prompt += " featuring unexpected details"

        return f"Digital artwork of {base_prompt}, digital art style"
