"""Activity for fetching news using web scraping."""

import logging
from typing import Dict, Any, List
from framework.activity_decorator import activity, ActivityBase, ActivityResult

logger = logging.getLogger(__name__)


@activity(
    name="fetch_news",
    energy_cost=0.3,
    cooldown=1800,  # 30 minutes
    required_skills=["web_scraping"],
)
class FetchNewsActivity(ActivityBase):
    def __init__(self):
        super().__init__()
        self.topics = ["technology", "science", "art"]
        self.max_articles = 5

    async def execute(self, shared_data) -> ActivityResult:
        """Execute the news fetching activity."""
        try:
            logger.info("Starting news fetch activity")

            # Simulate fetching news
            articles = await self._fetch_articles()

            # Store articles in shared data
            shared_data.set("memory", "latest_news", articles)

            logger.info(f"Successfully fetched {len(articles)} articles")
            return ActivityResult(
                success=True,
                data={"articles": articles, "count": len(articles)},
                metadata={"topics": self.topics, "max_articles": self.max_articles},
            )

        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return ActivityResult(success=False, error=str(e))

    async def _fetch_articles(self) -> List[Dict[str, Any]]:
        """Simulate fetching articles."""
        # In a real implementation, this would use web scraping
        articles = []
        for i in range(self.max_articles):
            articles.append(
                {
                    "title": f"Simulated Article {i+1}",
                    "topic": self.topics[i % len(self.topics)],
                    "summary": f"This is a simulated news article about {self.topics[i % len(self.topics)]}",
                    "url": f"https://example.com/article_{i+1}",
                }
            )
        return articles
