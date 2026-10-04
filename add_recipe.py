#!/usr/bin/env python3
"""Scrape a recipe from a URL and add it to Paprika as a new recipe."""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from heading_scraper import NoRecipeFound
from refresh_recipe import CACHE_DIR, PAPRIKA_API, get_paprika_token, scrape_recipe, upload_recipe


def new_recipe(category_uids: list[str]) -> dict:
    """An empty Paprika recipe with a fresh UID, to be filled in by scrape_recipe."""
    return {
        "uid":              str(uuid.uuid4()).upper(),
        "name":             "",
        "ingredients":      "",
        "directions":       "",
        "description":      "",
        "notes":            "",
        "nutritional_info": "",
        "servings":         "",
        "difficulty":       "",
        "prep_time":        "",
        "cook_time":        "",
        "total_time":       "",
        "source":           "",
        "source_url":       "",
        "image_url":        None,
        "photo":            None,
        "photo_hash":       None,
        "photo_large":      None,
        "photo_url":        None,
        "scale":            None,
        "hash":             "",
        "categories":       category_uids,
        "rating":           0,
        "in_trash":         False,
        "is_pinned":        False,
        "on_favorites":     False,
        "on_grocery_list":  False,
        "created":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_categories(token: str) -> list[dict]:
    resp = requests.get(f"{PAPRIKA_API}/v2/sync/categories/",
                        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["result"]


def resolve_categories(names: list[str], categories: list[dict]) -> list[str]:
    """Category UIDs for the given names; a name shared by several categories selects all of them."""
    by_name: dict[str, list[str]] = {}
    for c in categories:
        by_name.setdefault(c["name"].lower(), []).append(c["uid"])
    unknown = [n for n in names if n.lower() not in by_name]
    if unknown:
        available = ", ".join(sorted({c["name"] for c in categories if c["name"]}))
        raise ValueError(f"Unknown categories: {', '.join(unknown)}. Available: {available}")
    return [uid for n in names for uid in by_name[n.lower()]]


def find_existing_by_url(url: str, cache_dir: Path = CACHE_DIR) -> dict | None:
    """A cached, non-trashed recipe that was scraped from the same URL, if any."""
    for path in cache_dir.glob("*.json"):
        recipe = json.loads(path.read_text())
        if recipe.get("source_url") == url and not recipe.get("in_trash"):
            return recipe
    return None


def confirm(question: str, auto_yes: bool) -> bool:
    if auto_yes:
        print("Continuing due to --yes flag.")
        return True
    try:
        return input(f"{question} [y/N] ").strip().lower() == "y"
    except EOFError:
        print("Non-interactive terminal. Use --yes to force. Aborting.")
        return False


def login() -> str:
    email    = os.environ.get("PAPRIKA_EMAIL")
    password = os.environ.get("PAPRIKA_PASSWORD")
    if not email or not password:
        print("Error: set PAPRIKA_EMAIL and PAPRIKA_PASSWORD in .env or environment.")
        sys.exit(1)
    print("Authenticating with Paprika...")
    return get_paprika_token(email, password)


def main():
    parser = argparse.ArgumentParser(description="Scrape a recipe from a URL and add it to Paprika.")
    parser.add_argument("url", help="URL of the recipe to scrape")
    parser.add_argument("--category", "-c", action="append", default=[],
                        help="Paprika category name to assign (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape and print without uploading")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm any prompts")
    args = parser.parse_args()

    load_dotenv()

    duplicate = find_existing_by_url(args.url)
    if duplicate:
        print(f"Warning: '{duplicate['name']}' ({duplicate['uid']}) already has this source URL.")
        print(f"To update it instead: .venv/bin/python refresh_recipe.py {duplicate['uid']}")
        if not confirm("Add it as a new recipe anyway?", args.yes):
            sys.exit(1)

    token = None
    category_uids = []
    if args.category:
        token = login()
        try:
            category_uids = resolve_categories(args.category, fetch_categories(token))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    print(f"Scraping: {args.url}")
    try:
        recipe, photo_bytes = scrape_recipe(args.url, new_recipe(category_uids))
    except requests.RequestException as e:
        print(f"Error: could not fetch the recipe page: {e}")
        sys.exit(1)
    except NoRecipeFound:
        print("Error: no recipe found on this page (no recipe data, and no ingredients/directions headings).")
        sys.exit(1)
    print(f"Scraped:  {recipe['name']}")

    ingredients = [s for s in recipe["ingredients"].split("\n") if s.strip()]
    steps       = [s for s in recipe["directions"].split("\n") if s.strip()]
    print(f"  ingredients: {len(ingredients)}, directions: {len(steps)} steps")

    if args.dry_run:
        preview = {**recipe, "photo": f"<{len(photo_bytes)} bytes>" if photo_bytes else None}
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        return

    if not recipe["name"] or not steps:
        print("Warning: the scraped recipe has no name or no directions.")
        if not confirm("Add it anyway?", args.yes):
            sys.exit(1)

    if token is None:
        token = login()

    print("Uploading to Paprika...")
    upload_recipe(recipe, photo_bytes, token)
    print(f"  Added with UID {recipe['uid']}")

    print("Opening in browser...")
    subprocess.run(["ruby", Path(__file__).parent / "show_recipe.rb", recipe["uid"]], check=True)

    print("Done!")


if __name__ == "__main__":
    main()
