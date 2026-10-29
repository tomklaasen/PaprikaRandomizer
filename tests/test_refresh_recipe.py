#!/usr/bin/env python3
"""Tests for the directions fallback policy in refresh_recipe.py.

Parsing a real page is covered by the dagelijksekost-scraper package; these tests only pin down
which source this script prefers.

Run with: .venv/bin/python -m unittest discover tests
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refresh_recipe import scrape_directions, scrape_recipe

DAGELIJKSEKOST_URL = "https://dagelijksekost.vrt.be/gerechten/iets"
OTHER_URL          = "https://example.com/recipes/iets"

_payload = json.dumps({"recipeParts": [{"title": None, "instructions": [
    {"part": 1, "step": 1, "description": "Stap uit de payload.", "tip": None},
]}]})
PAGE_WITH_PAYLOAD    = f"<html><script>self.__next_f.push([1,{json.dumps(_payload)}])</script></html>"
PAGE_WITHOUT_PAYLOAD = "<html><body>geen payload</body></html>"


class FakeScraper:
    """Stands in for a recipe_scrapers scraper, which can only be built from a full page."""

    def __init__(self, instructions="Stap van de scraper."):
        self._instructions = instructions

    def instructions(self):
        if self._instructions is None:
            raise ValueError("no instructions in this page")
        return self._instructions


class ScrapeDirectionsTest(unittest.TestCase):
    def test_prefers_the_payload_for_dagelijksekost(self):
        directions = scrape_directions(FakeScraper(), PAGE_WITH_PAYLOAD, DAGELIJKSEKOST_URL)

        self.assertEqual("Stap uit de payload.", directions)

    def test_falls_back_to_the_scraper_when_dagelijksekost_has_no_payload(self):
        directions = scrape_directions(FakeScraper(), PAGE_WITHOUT_PAYLOAD, DAGELIJKSEKOST_URL)

        self.assertEqual("Stap van de scraper.", directions)

    def test_uses_the_scraper_for_other_hosts(self):
        directions = scrape_directions(FakeScraper(), PAGE_WITH_PAYLOAD, OTHER_URL)

        self.assertEqual("Stap van de scraper.", directions)

    def test_returns_an_empty_string_when_the_scraper_fails(self):
        directions = scrape_directions(FakeScraper(instructions=None), PAGE_WITHOUT_PAYLOAD, DAGELIJKSEKOST_URL)

        self.assertEqual("", directions)


if __name__ == "__main__":
    unittest.main()


SAVED_PAGE = """<html><head><script type="application/ld+json">{"@context": "https://schema.org",
"@type": "Recipe", "name": "Erwtensoep", "recipeIngredient": ["500 g spliterwten"],
"recipeInstructions": [{"@type": "HowToStep", "text": "Kook de erwten."}]}</script></head></html>"""


class ScrapeRecipeTest(unittest.TestCase):
    def test_uses_a_saved_page_without_fetching_the_url(self):
        with mock.patch("refresh_recipe.requests.get", side_effect=AssertionError("fetched")):
            recipe, _ = scrape_recipe(OTHER_URL, {"name": ""}, SAVED_PAGE)

        self.assertEqual("500 g spliterwten", recipe["ingredients"])
        self.assertEqual("Kook de erwten.", recipe["directions"])
        self.assertEqual(OTHER_URL, recipe["source_url"])
