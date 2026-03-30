#!/usr/bin/env python3
"""Re-scrape a recipe from a new URL and update it in Paprika, preserving its UID and categories."""

import argparse
import gzip
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from recipe_scrapers import scrape_html

PAPRIKA_API = "https://www.paprikaapp.com/api"
CACHE_DIR      = Path(__file__).parent / "cache"
HTML_CACHE_DIR = Path(__file__).parent / "html_cache"


def get_paprika_token(email: str, password: str) -> str:
    resp = requests.post(f"{PAPRIKA_API}/v1/account/login/",
                         data={"email": email, "password": password}, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["token"]


def format_minutes(minutes: int) -> str:
    if not minutes or minutes <= 0:
        return ""
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"


def compute_hash(recipe: dict) -> str:
    fields = {k: v for k, v in recipe.items() if k != "hash"}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def fetch_photo(image_url: str | None) -> tuple[dict, bytes | None]:
    if not image_url:
        return {"photo": None, "photo_hash": None, "photo_large": None}, None
    try:
        resp = requests.get(image_url, timeout=10)
        resp.raise_for_status()
        data = resp.content
        return {"photo": f"{uuid.uuid4()}.jpg", "photo_hash": hashlib.sha256(data).hexdigest(), "photo_large": None}, data
    except Exception as e:
        print(f"  Warning: could not fetch photo: {e}")
        return {"photo": None, "photo_hash": None, "photo_large": None}, None


HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}


def scrape_recipe(url: str, existing: dict) -> tuple[dict, bytes | None]:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    try:
        scraper = scrape_html(html, org_url=url)
    except Exception:
        scraper = scrape_html(html, org_url=url, wild_mode=True)

    og_title = soup.find("meta", property="og:title")
    name = og_title["content"] if og_title and og_title.get("content") else (
        soup.find("h1").get_text(strip=True) if soup.find("h1") else existing["name"]
    )

    def safe(fn, default=None):
        try:
            result = fn()
            return result if result is not None else default
        except Exception:
            return default

    image_url = safe(scraper.image)
    photo_fields, photo_bytes = fetch_photo(image_url)

    recipe = {
        **existing,                                        # start from existing (preserves uid, categories, rating, etc.)
        "name":           name,
        "ingredients":    "\n".join(safe(scraper.ingredients, [])),
        "directions":     safe(scraper.instructions, ""),
        "description":    safe(scraper.description, ""),
        "source":         safe(scraper.host) or requests.utils.urlparse(url).netloc,
        "source_url":     url,
        "prep_time":      format_minutes(safe(scraper.prep_time, 0)),
        "cook_time":      format_minutes(safe(scraper.cook_time, 0)),
        "total_time":     format_minutes(safe(scraper.total_time, 0)),
        "servings":       safe(scraper.yields, ""),
        "image_url":      image_url,
        **photo_fields,
        "photo_url":      None,
        "hash":           "",
    }
    recipe["hash"] = compute_hash(recipe)
    return recipe, photo_bytes


def upload_recipe(recipe: dict, photo_bytes: bytes | None, token: str) -> None:
    compressed = gzip.compress(json.dumps(recipe).encode())
    files = {"data": compressed}
    if photo_bytes:
        files["photo_upload"] = (recipe["photo"], photo_bytes, "image/jpeg")

    resp = requests.post(
        f"{PAPRIKA_API}/v2/sync/recipe/{recipe['uid']}/",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        timeout=30,
    )
    resp.raise_for_status()
    if not resp.json().get("result"):
        raise RuntimeError(f"Paprika upload failed: {resp.json()}")


BACKUP_DIR = Path(__file__).parent / "backup"


def backup_and_clear_cache(uid: str) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = CACHE_DIR / f"{uid}.json"
    if json_path.exists():
        backup_path = BACKUP_DIR / f"{uid}_{timestamp}.json"
        json_path.rename(backup_path)
        print(f"  Backed up to {backup_path.name}")

    html_path = HTML_CACHE_DIR / f"{uid}.html"
    if html_path.exists():
        html_path.unlink()
        print(f"  Cleared {html_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Re-scrape a recipe from a new URL and update it in Paprika.")
    parser.add_argument("uid",  help="UID of the existing Paprika recipe to update")
    parser.add_argument("url", nargs="?", default=None, help="URL to scrape (defaults to the recipe's stored source_url)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape and print without uploading")
    args = parser.parse_args()

    load_dotenv()

    cache_file = CACHE_DIR / f"{args.uid}.json"
    if not cache_file.exists():
        print(f"Error: no cached recipe found for UID {args.uid}")
        sys.exit(1)

    existing = json.loads(cache_file.read_text())
    url = args.url or existing.get("source_url")
    if not url:
        print("Error: no URL provided and recipe has no stored source_url.")
        sys.exit(1)
    print(f"Existing recipe: {existing['name']}")
    print(f"Scraping: {url}")

    recipe, photo_bytes = scrape_recipe(url, existing)
    print(f"Scraped:  {recipe['name']}")

    if args.dry_run:
        preview = {**recipe, "photo": f"<{len(photo_bytes)} bytes>" if photo_bytes else None}
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        return

    email    = os.environ.get("PAPRIKA_EMAIL")
    password = os.environ.get("PAPRIKA_PASSWORD")
    if not email or not password:
        print("Error: set PAPRIKA_EMAIL and PAPRIKA_PASSWORD in .env or environment.")
        sys.exit(1)

    print("Authenticating with Paprika...")
    token = get_paprika_token(email, password)

    print("Uploading to Paprika...")
    upload_recipe(recipe, photo_bytes, token)

    print("Backing up and clearing local cache...")
    backup_and_clear_cache(args.uid)

    print("Opening in browser...")
    import subprocess
    subprocess.run(["ruby", Path(__file__).parent / "show_recipe.rb", args.uid], check=True)

    print("Done!")


if __name__ == "__main__":
    main()
