#!/usr/bin/env python3
"""Restore a recipe from a backup and re-upload it to Paprika."""

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

PAPRIKA_API    = "https://www.paprikaapp.com/api"
CACHE_DIR      = Path(__file__).parent / "cache"
HTML_CACHE_DIR = Path(__file__).parent / "html_cache"
BACKUP_DIR     = Path(__file__).parent / "backup"


def get_paprika_token(email: str, password: str) -> str:
    resp = requests.post(f"{PAPRIKA_API}/v1/account/login/",
                         data={"email": email, "password": password}, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["token"]


def upload_recipe(recipe: dict, token: str) -> None:
    compressed = gzip.compress(json.dumps(recipe).encode())
    resp = requests.post(
        f"{PAPRIKA_API}/v2/sync/recipe/{recipe['uid']}/",
        headers={"Authorization": f"Bearer {token}"},
        files={"data": compressed},
        timeout=30,
    )
    resp.raise_for_status()
    if not resp.json().get("result"):
        raise RuntimeError(f"Paprika upload failed: {resp.json()}")


def main():
    parser = argparse.ArgumentParser(description="Restore a recipe from a backup.")
    parser.add_argument("uid", help="UID of the recipe to restore")
    parser.add_argument("backup", nargs="?", help="Backup timestamp or filename (omit to pick interactively)")
    args = parser.parse_args()

    load_dotenv()

    backups = sorted(BACKUP_DIR.glob(f"{args.uid}_*.json"))
    if not backups:
        print(f"No backups found for UID {args.uid}")
        sys.exit(1)

    if args.backup:
        # accept either a full filename or just the timestamp part
        match = next((b for b in backups if args.backup in b.name), None)
        if not match:
            print(f"No backup matching '{args.backup}' found. Available:")
            for b in backups:
                print(f"  {b.name}")
            sys.exit(1)
        backup_file = match
    elif len(backups) == 1:
        backup_file = backups[0]
    else:
        print("Available backups:")
        for i, b in enumerate(backups):
            print(f"  [{i}] {b.name}")
        choice = input("Restore which? [0]: ").strip() or "0"
        backup_file = backups[int(choice)]

    recipe = json.loads(backup_file.read_text())
    print(f"Restoring: {recipe['name']} from {backup_file.name}")

    email    = os.environ.get("PAPRIKA_EMAIL")
    password = os.environ.get("PAPRIKA_PASSWORD")
    if not email or not password:
        print("Error: set PAPRIKA_EMAIL and PAPRIKA_PASSWORD in .env or environment.")
        sys.exit(1)

    print("Authenticating with Paprika...")
    token = get_paprika_token(email, password)

    print("Uploading to Paprika...")
    upload_recipe(recipe, token)

    print("Restoring local cache...")
    shutil.copy(backup_file, CACHE_DIR / f"{args.uid}.json")
    html_path = HTML_CACHE_DIR / f"{args.uid}.html"
    if html_path.exists():
        html_path.unlink()

    print("Opening in browser...")
    subprocess.run(["ruby", Path(__file__).parent / "show_recipe.rb", args.uid], check=True)

    print("Done!")


if __name__ == "__main__":
    main()
