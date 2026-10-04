"""Fallback scraper for recipe pages without a Recipe schema, such as most Blogger posts.

It looks for an "Ingrediënten"-style heading and a "Werkwijze"-style heading in the post body, and
reads the list items under each. It implements the subset of the recipe-scrapers interface that
refresh_recipe.scrape_recipe uses.
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

INGREDIENTS_HEADING = re.compile(r"(?i)^(ingredi[eë]nten|ingredients|benodigdheden|wat heb je nodig\??)$")
DIRECTIONS_HEADING  = re.compile(r"(?i)^(werkwijze|bereiding|bereidingswijze|instructies|"
                                 r"directions|instructions|method|preparation)$")

CONTENT_SELECTORS = [".post-body", ".entry-content", "article", "main", "body"]
BLOCK_TAGS = {"p", "div", "section", "article", "ul", "ol", "table", "tr", "td", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS  = {"script", "style", "noscript"}


class NoRecipeFound(Exception):
    pass


class Line:
    def __init__(self, text: str, is_item: bool):
        self.text    = text
        self.is_item = is_item


def _lines(container: Tag) -> list[Line]:
    """The container's text as lines, keeping track of which lines are list items."""
    lines: list[Line] = []
    buffer: list[str] = []

    def flush():
        text = " ".join("".join(buffer).split())
        buffer.clear()
        if text:
            lines.append(Line(text, is_item=False))

    def walk(el: Tag):
        for child in el.children:
            if isinstance(child, NavigableString):
                buffer.append(str(child))
            elif not isinstance(child, Tag) or child.name in SKIP_TAGS:
                continue
            elif child.name == "br":
                flush()
            elif child.name == "li":
                flush()
                text = " ".join(child.get_text(" ").split())
                if text:
                    lines.append(Line(text, is_item=True))
            elif child.name in BLOCK_TAGS:
                flush()
                walk(child)
                flush()
            else:
                walk(child)

    walk(container)
    flush()
    return lines


def _heading_text(line: Line) -> str:
    return line.text.rstrip(":").strip()


def _followed_by_item(lines: list[Line], i: int) -> bool:
    return i + 1 < len(lines) and lines[i + 1].is_item


class HeadingScraper:
    def __init__(self, html: str, url: str):
        self.url  = url
        self.soup = BeautifulSoup(html, "html.parser")
        container = next((c for c in (self.soup.select_one(s) for s in CONTENT_SELECTORS) if c), self.soup)
        lines = _lines(container)

        start = next((i for i, l in enumerate(lines)
                      if not l.is_item and INGREDIENTS_HEADING.match(_heading_text(l))), None)
        end   = next((i for i, l in enumerate(lines)
                      if start is not None and i > start
                      and not l.is_item and DIRECTIONS_HEADING.match(_heading_text(l))), None)
        if start is None or end is None:
            raise NoRecipeFound(f"No ingredients and directions headings found at {url}")

        self._intro = [l.text for l in lines[:start]]
        self._ingredients, self._extras = self._split_ingredients(lines[start + 1:end])
        self._directions = self._directions_from(lines[end + 1:])

    @staticmethod
    def _split_ingredients(lines: list[Line]) -> tuple[list[str], list[str]]:
        """List items are ingredients (with the line just above a list as a sub-heading); other lines are extras."""
        if not any(l.is_item for l in lines):
            return [l.text for l in lines], []
        ingredients, extras = [], []
        for i, line in enumerate(lines):
            if line.is_item or _followed_by_item(lines, i):
                ingredients.append(line.text)
            else:
                extras.append(line.text)
        return ingredients, extras

    @staticmethod
    def _directions_from(lines: list[Line]) -> list[str]:
        """Steps up to the last list item; a line just above a list becomes an uppercase section header."""
        last_item = max((i for i, l in enumerate(lines) if l.is_item), default=None)
        if last_item is None:
            return [l.text for l in lines]
        return [l.text.upper() if not l.is_item and _followed_by_item(lines, i) else l.text
                for i, l in enumerate(lines[:last_item + 1])]

    def ingredients(self) -> list[str]:
        return self._ingredients

    def instructions(self) -> str:
        return "\n".join(self._directions)

    def description(self) -> str:
        parts = ["\n".join(self._intro), "\n".join(self._extras)]
        return "\n\n".join(p for p in parts if p)

    def image(self) -> str | None:
        og = self.soup.find("meta", property="og:image")
        return og.get("content") if og else None

    def host(self) -> str:
        return urlparse(self.url).netloc

    def prep_time(self):
        return None

    def cook_time(self):
        return None

    def total_time(self):
        return None

    def yields(self):
        return None
