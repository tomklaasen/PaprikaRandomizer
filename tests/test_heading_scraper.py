#!/usr/bin/env python3
"""Tests for heading_scraper.py, the fallback for pages without a Recipe schema.

Run with: .venv/bin/python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heading_scraper import HeadingScraper, NoRecipeFound

URL = "https://iemand.blogspot.com/2024/03/taartjes.html"

# Shaped like a Blogger post: headings are bare paragraphs, some paragraphs hold several lines.
BLOG_POST = """
<html><head>
  <meta property="og:image" content="https://img.example/taart.jpg">
</head><body>
  <div class="sidebar"><ul><li>Archief 2023</li></ul></div>
  <div class="post-body">
    <p>Een heerlijk recept.</p>
    <p>Tip: maak de karamel op voorhand.</p>
    <p>Ingrediënten</p>
    <ul><li>2 eieren</li><li>100 g suiker</li></ul>
    <p>Extra nodig<br>bakplaat</p>
    <p>Werkwijze<br>Deeg</p>
    <ul><li>Klop de eieren.</li><li>Voeg de suiker toe.</li></ul>
    <p>Afwerken</p>
    <ul><li>Bak 20 minuten.</li></ul>
  </div>
</body></html>
"""


class HeadingScraperTest(unittest.TestCase):
    def setUp(self):
        self.scraper = HeadingScraper(BLOG_POST, URL)

    def test_takes_the_list_items_after_the_ingredients_heading(self):
        self.assertEqual(["2 eieren", "100 g suiker"], self.scraper.ingredients())

    def test_takes_the_steps_after_the_directions_heading_with_uppercase_section_headers(self):
        self.assertEqual(
            "DEEG\nKlop de eieren.\nVoeg de suiker toe.\nAFWERKEN\nBak 20 minuten.",
            self.scraper.instructions(),
        )

    def test_keeps_the_intro_and_the_extras_as_description(self):
        self.assertEqual(
            "Een heerlijk recept.\nTip: maak de karamel op voorhand.\n\nExtra nodig\nbakplaat",
            self.scraper.description(),
        )

    def test_reads_image_and_host_from_the_page(self):
        self.assertEqual("https://img.example/taart.jpg", self.scraper.image())
        self.assertEqual("iemand.blogspot.com", self.scraper.host())

    def test_takes_plain_lines_when_the_ingredients_are_not_a_list(self):
        html = """<div class="entry-content">
          <h3>Ingredients</h3><p>2 eggs<br>100 g sugar</p>
          <h3>Bereiding</h3><p>Mix.</p><p>Bake.</p>
        </div>"""
        scraper = HeadingScraper(html, URL)

        self.assertEqual(["2 eggs", "100 g sugar"], scraper.ingredients())
        self.assertEqual("Mix.\nBake.", scraper.instructions())

    def test_raises_when_there_are_no_recognisable_headings(self):
        with self.assertRaises(NoRecipeFound):
            HeadingScraper("<html><body><p>Gewoon een blogpost.</p></body></html>", URL)


if __name__ == "__main__":
    unittest.main()
