#!/usr/bin/env python3
"""Tests for the site-specific directions extraction in refresh_recipe.py.

Run with: .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recipe_scrapers import scrape_html

from refresh_recipe import dagelijksekost_directions, scrape_directions

FIXTURE_URL = "https://dagelijksekost.vrt.be/gerechten/veggie-okonomiyaki"
FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "dagelijksekost_veggie_okonomiyaki.html").read_text(encoding="utf-8")

FIRST_STEP = "Laat de gedroogde paddenstoelen en de kombu minstens een uur weken in koud water."
LAST_STEP  = "Werk af met streepjes okonomiyakisaus en kewpie mayonaise."


class DagelijkseKostDirectionsTest(unittest.TestCase):
    def test_extracts_every_step_from_the_rsc_payload(self):
        steps = [s for s in dagelijksekost_directions(FIXTURE_HTML).split("\n") if not s.startswith("Tip: ")]

        self.assertEqual(15, len(steps))
        self.assertEqual(FIRST_STEP, steps[0])
        self.assertEqual(LAST_STEP, steps[-1])

    def test_keeps_the_tip_that_belongs_to_a_step(self):
        lines = dagelijksekost_directions(FIXTURE_HTML).split("\n")

        self.assertIn("Tip: Of laat een scheut olie heet worden in een anti-kleefpan, schep het beslag in de pan, "
                      "laat de onderkant zacht bakken, draai de pannenkoek om en bak ze nog even op de andere kant.",
                      lines)

    def test_returns_none_when_the_page_has_no_rsc_payload(self):
        self.assertIsNone(dagelijksekost_directions("<html><body>geen payload</body></html>"))


class ScrapeDirectionsTest(unittest.TestCase):
    def setUp(self):
        self.scraper = scrape_html(FIXTURE_HTML, org_url=FIXTURE_URL)

    def test_json_ld_alone_is_incomplete(self):
        """Guards the premise of the fix: without it we only get the truncated JSON-LD steps."""
        self.assertEqual(2, len(self.scraper.instructions().split("\n")))

    def test_prefers_the_full_payload_for_dagelijksekost(self):
        directions = scrape_directions(self.scraper, FIXTURE_HTML, FIXTURE_URL)

        self.assertEqual(FIRST_STEP, directions.split("\n")[0])
        self.assertIn(LAST_STEP, directions.split("\n"))

    def test_falls_back_to_the_scraper_for_other_hosts(self):
        directions = scrape_directions(self.scraper, FIXTURE_HTML, "https://example.com/gerechten/veggie-okonomiyaki")

        self.assertEqual(self.scraper.instructions(), directions)


if __name__ == "__main__":
    unittest.main()
