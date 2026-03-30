# PaprikaRandomizer

Can't decide what to cook for dinner? This script picks a random main course from your [Paprika Recipe Manager](https://www.paprikaapp.com/) library.

## Setup

```
bundle install
cp .env.example .env
```

Edit `.env` with your Paprika account credentials.

## Usage

```
ruby main.rb
```

The first run fetches all your recipes from the Paprika API and caches them locally. Subsequent runs are instant — only new or updated recipes are re-fetched.
