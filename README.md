# PaprikaRandomizer

A set of scripts for browsing your [Paprika Recipe Manager](https://www.paprikaapp.com/) library from the command line, with recipes displayed as styled HTML pages in the browser.

## Setup

```
bundle install
cp .env.example .env
```

Edit `.env` with your Paprika account credentials.

For `refresh_recipe.py`, also set up the Python environment:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Scripts

### `ruby randomizer.rb`

Picks a random main course (category: Hoofdgerecht) from your Paprika library and opens it as a styled HTML page.

### `ruby plan.rb`

Shows the next 14 days of your Paprika meal plan. Recipes that are cached locally are shown as clickable links.

### `.venv/bin/python add_recipe.py <url> [-c <category>]...`

Scrapes a recipe from a URL and adds it to Paprika as a new recipe, then opens it in the browser. Uses the
same scraping as `refresh_recipe.py` (including the dagelijksekost.vrt.be directions).

```
# Add a recipe, assigning one or more categories by name (case-insensitive)
.venv/bin/python add_recipe.py https://dagelijksekost.vrt.be/gerechten/... -c Hoofdgerecht -c Vlees

# Inspect what would be added, without uploading
.venv/bin/python add_recipe.py --dry-run https://...
```

- An unknown category name aborts with the list of available categories. A name shared by several
  categories assigns all of them.
- If a locally cached recipe already has the same source URL, it asks before adding a duplicate and
  suggests `refresh_recipe.py` instead.
- If the scraped recipe has no name or no directions, it asks before uploading.
- `--yes` / `-y` auto-confirms these prompts.

### `.venv/bin/python refresh_recipe.py <uid> [url]`

Re-scrapes a recipe and updates it in Paprika, preserving the original UID and categories. If no URL is given, the recipe's stored source URL is used. Useful when a recipe's content has changed or moved to a new URL.

```
# Re-scrape from the stored URL
.venv/bin/python refresh_recipe.py <recipe-uid>

# Re-scrape from a new URL
.venv/bin/python refresh_recipe.py <recipe-uid> https://dagelijksekost.vrt.be/gerechten/...
```

Works with any site supported by [recipe-scrapers](https://github.com/hhursev/recipe-scrapers), with a generic fallback for unsupported sites. Pages without any recipe data (such as most Blogger posts) are read by `heading_scraper.py`, which takes the list items under an "Ingrediënten"-style heading and a "Werkwijze"-style heading; a line just above a list of steps becomes an uppercase section header. Before overwriting, the previous version is saved to `backup/<uid>_<timestamp>.json`.

The script checks the scraped directions before uploading:
- If directions are **empty**, it aborts to prevent data loss.
- If directions have **fewer than 50% of the original steps**, it asks for confirmation before continuing.

For `dagelijksekost.vrt.be` the directions come from
[dagelijksekost-scraper](https://github.com/tomklaasen/dagelijksekost-scraper), which reads them from the
page's Next.js payload: that site's JSON-LD only lists the first two steps, and the fallback in
recipe-scrapers still expects the site's older data format. Step tips are kept as a `Tip: ...` line. If
that payload is ever gone, the script falls back to whatever recipe-scrapers finds.

```
.venv/bin/python -m unittest discover tests
```

### `.venv/bin/python restore_recipe.py <uid> [timestamp]`

Restores a recipe from a backup and re-uploads it to Paprika. If no timestamp is given and multiple backups exist, you'll be prompted to pick one.

```
# Pick interactively
.venv/bin/python restore_recipe.py <recipe-uid>

# Restore a specific version
.venv/bin/python restore_recipe.py <recipe-uid> 20260330_143000
```

### `ruby history.rb`

Shows all recipes that have appeared in your meal plan, sorted by how many times they were made. Each entry lists the count and all the dates. Recipes cached locally are shown as clickable links.

### `ruby backup_all.rb`

Syncs all recipes from Paprika and renders every recipe as a styled HTML page. Suitable for running as a cronjob on another machine to keep a full local backup up to date.

```
# Example crontab entry — run every night at 2 AM
0 2 * * * cd /path/to/PaprikaRandomizer && ruby backup_all.rb >> /var/log/paprika_backup.log 2>&1
```

Both the JSON files (`cache/`) and HTML pages (`html_cache/`) are updated. Only recipes that have changed since the last run are re-fetched from Paprika; unchanged ones are served from the local cache. An `html_cache/index.html` is also generated, listing all recipes grouped by category with a live search filter.

Requests to the Paprika API use a 30s connect / 60s read timeout and retry up to 3 times with exponential backoff on transient network errors, so brief outages don't fail the whole sync.

To monitor the cronjob with [healthchecks.io](https://healthchecks.io), set `HEALTHCHECKS_URL` in `.env` to your check's ping URL. The script pings `/start` at the beginning, the base URL on success, and `/fail` on error.

## Caching

The first run of `randomizer.rb` or `plan.rb` fetches all 800+ recipes from the Paprika API and caches them locally in `cache/`. Subsequent runs are instant — only new or updated recipes are re-fetched. Rendered HTML pages are cached in `html_cache/`.
