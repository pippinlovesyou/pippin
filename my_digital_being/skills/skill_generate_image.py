"""Image generation skill implementation."""

import logging
from typing import Dict, Any, Tuple
import random
from framework.api_management import api_manager

logger = logging.getLogger(__name__)


class ImageGenerationSkill:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the image generation skill with secure API key handling."""
        self.enabled = config.get("enabled", False)
        self.max_generations = config.get("max_generations_per_day", 50)
        self.supported_formats = config.get("supported_formats", ["png", "jpg"])
        self.generations_count = 0

        # Register required API keys
        api_manager.register_required_keys("image_generation", ["OPENAI"])

    async def can_generate(self) -> bool:
        """Check if image generation is allowed."""
        if not self.enabled:
            logger.warning("Image generation is disabled")
            return False

        if self.generations_count >= self.max_generations:
            logger.warning("Daily generation limit reached")
            return False

        # Verify API key exists and is configured
        api_key = await api_manager.check_api_key_exists("image_generation", "OPENAI")
        if not api_key:
            logger.error("OpenAI API key not configured for image generation")
            return False

        return True

    async def generate_image(
        self, prompt: str, size: Tuple[int, int] = (512, 512), format: str = "png"
    ) -> Dict[str, Any]:
        """Generate an image based on the prompt."""
        if not await self.can_generate():
            error_msg = "Image generation is not available (disabled, limit reached, or not configured)"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        if format not in self.supported_formats:
            error_msg = f"Unsupported format. Use: {self.supported_formats}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        try:
            # Get API key from api_manager
            api_key = await api_manager.get_api_key("image_generation", "OPENAI")
            if not api_key:
                error_msg = "OpenAI API key not configured"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # In a real implementation, this would use the API key to call the image generation service
            logger.info(f"Generating image for prompt: {prompt}")

            # Increment counter only on successful generation
            self.generations_count += 1

            # Simulate generation result
            image_data = {
                "width": size[0],
                "height": size[1],
                "format": format,
                "seed": random.randint(1000, 9999),
                "generation_id": f"gen_{self.generations_count}",
            }

            return {
                "success": True,
                "image_data": image_data,
                "metadata": {
                    "prompt": prompt,
                    "generation_number": self.generations_count,
                },
            }
        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            return {"success": False, "error": str(e)}

    def reset_counts(self):
        """Reset the generation counter."""
        self.generations_count = 0
