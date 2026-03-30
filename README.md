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

### `.venv/bin/python refresh_recipe.py <uid> <url>`

Re-scrapes a recipe from a new URL and updates it in Paprika, preserving the original UID and categories. Useful when a recipe has moved to a new URL.

```
.venv/bin/python refresh_recipe.py <recipe-uid> https://dagelijksekost.vrt.be/gerechten/...
```

## Caching

The first run of `randomizer.rb` or `plan.rb` fetches all 800+ recipes from the Paprika API and caches them locally in `cache/`. Subsequent runs are instant — only new or updated recipes are re-fetched. Rendered HTML pages are cached in `html_cache/`.
