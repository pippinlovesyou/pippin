"""
Web Scraping Skill
Uses requests + BeautifulSoup to scrape and parse web content.
No external API keys are required.
"""

import logging
from typing import Optional, List, Dict, Any
import requests
from bs4 import BeautifulSoup
from framework.api_management import (
    api_manager,
)  # For consistency, though no keys are used

logger = logging.getLogger(__name__)


class WebScrapingSkill:
    """
    Skill for basic web scraping using requests and BeautifulSoup.
    No API key required.
    """

    def __init__(self):
        self.skill_name = "web_scraping"
        # This skill does not require API keys, but we can still register it
        # with api_manager if we want consistent skill management
        api_manager.register_required_keys(self.skill_name, [])

    async def scrape(self, url: str, parse: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch the HTML content from a URL. If parse=True, parse HTML with BeautifulSoup
        and return a structured representation.

        Returns:
            Dict with keys:
              - 'status_code': HTTP status
              - 'content': raw HTML
              - 'parsed': optional parse result (if parse=True)
            or None if error
        """
        try:
            logger.info(f"Scraping URL: {url}")
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()

            result = {"status_code": resp.status_code, "content": resp.text}

            if parse:
                soup = BeautifulSoup(resp.text, "html.parser")
                # You could add logic to extract links, headings, etc.
                # For now, we just store the "soup" as a string or partial structure
                # But you can store it as you like
                result["parsed"] = {
                    "title": soup.title.string if soup.title else None,
                    "body_text": soup.get_text(strip=True)[0:500],  # example snippet
                }

            return result
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}", exc_info=True)
            return None
