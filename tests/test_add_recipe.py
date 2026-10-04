#!/usr/bin/env python3
"""Tests for the pure helpers in add_recipe.py.

Scraping and uploading are shared with refresh_recipe.py; these tests cover what is specific to
creating a new recipe.

Run with: .venv/bin/python -m unittest discover tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from add_recipe import find_existing_by_url, new_recipe, resolve_categories

CATEGORIES = [
    {"uid": "UID-HOOFD", "name": "Hoofdgerecht"},
    {"uid": "UID-SOEP",  "name": "Soep"},
]


class NewRecipeTest(unittest.TestCase):
    def test_has_a_fresh_uppercase_uid(self):
        first, second = new_recipe([]), new_recipe([])

        self.assertNotEqual(first["uid"], second["uid"])
        self.assertEqual(first["uid"].upper(), first["uid"])

    def test_starts_empty_with_the_given_categories(self):
        recipe = new_recipe(["UID-SOEP"])

        self.assertEqual(["UID-SOEP"], recipe["categories"])
        self.assertEqual("", recipe["notes"])
        self.assertEqual(0, recipe["rating"])
        self.assertFalse(recipe["in_trash"])
        self.assertRegex(recipe["created"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class ResolveCategoriesTest(unittest.TestCase):
    def test_matches_names_case_insensitively(self):
        self.assertEqual(["UID-HOOFD", "UID-SOEP"], resolve_categories(["hoofdgerecht", "SOEP"], CATEGORIES))

    def test_assigns_every_category_that_shares_a_name(self):
        categories = CATEGORIES + [{"uid": "UID-SOEP-2", "name": "Soep"}]

        self.assertEqual(["UID-SOEP", "UID-SOEP-2"], resolve_categories(["Soep"], categories))

    def test_rejects_unknown_names(self):
        with self.assertRaisesRegex(ValueError, "Dessert"):
            resolve_categories(["Dessert"], CATEGORIES)


class FindExistingByUrlTest(unittest.TestCase):
    def test_finds_a_cached_recipe_with_the_same_source_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "A.json").write_text(json.dumps({"uid": "A", "name": "Soep", "source_url": "https://x.be/soep"}))
            (cache / "B.json").write_text(json.dumps({"uid": "B", "name": "Pasta", "source_url": "https://x.be/pasta"}))

            found = find_existing_by_url("https://x.be/pasta", cache)

        self.assertEqual("B", found["uid"])

    def test_ignores_recipes_in_the_trash(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "A.json").write_text(json.dumps({"uid": "A", "source_url": "https://x.be/soep", "in_trash": True}))

            self.assertIsNone(find_existing_by_url("https://x.be/soep", cache))


if __name__ == "__main__":
    unittest.main()
