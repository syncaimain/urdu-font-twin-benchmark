"""Fetch revision-pinned, openly licensed Urdu Wikipedia source sentences."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path


API_URL = "https://ur.wikipedia.org/w/api.php"
LICENSE = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
TITLES = [
    "پاکستان",
    "اردو",
    "پشاور",
    "کراچی",
    "اسلام آباد",
    "دریائے سندھ",
    "سائنس",
    "کمپیوٹر",
    "تعلیم",
    "کتاب",
    "بارش",
    "زمین",
    "نظام شمسی",
    "پانی",
    "تاریخ",
]


def _first_sentence(extract: str) -> str:
    text = extract
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\([^()]*\)", " ", text)
    allowed_punctuation = " ،۔؟؛:—-"
    text = "".join(
        char
        for char in text
        if char in allowed_punctuation
        or "\u0600" <= char <= "\u08ff"
        or char.isdecimal()
        or unicodedata.category(char).startswith("Z")
    )
    text = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"^.*?[۔؟!]", text)
    return (match.group(0) if match else text[:400]).strip()


def fetch_sources(output: Path) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "prop": "extracts|revisions|info",
        "exintro": "1",
        "explaintext": "1",
        "rvprop": "ids|timestamp",
        "inprop": "url",
        "titles": "|".join(TITLES),
    }
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "UrduFontTwinBenchmark/0.1 (research benchmark)"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)

    pages = {page["title"]: page for page in payload["query"]["pages"]}
    rows: list[dict] = []
    for index, requested_title in enumerate(TITLES, start=1):
        page = pages.get(requested_title)
        if page is None:
            page = next(
                (candidate for candidate in pages.values() if candidate.get("title") == requested_title),
                None,
            )
        if not page or page.get("missing"):
            raise RuntimeError(f"Wikipedia page missing: {requested_title}")
        revision = page["revisions"][0]
        sentence = _first_sentence(page.get("extract", ""))
        if len(sentence.split()) < 3:
            raise RuntimeError(f"No usable sentence found for {requested_title!r}")
        rows.append(
            {
                "source_id": f"wiki-ur-{index:02d}",
                "requested_title": requested_title,
                "page_title": page["title"],
                "text": sentence,
                "revision_id": revision["revid"],
                "parent_revision_id": revision.get("parentid"),
                "revision_timestamp": revision["timestamp"],
                "source_url": page["fullurl"],
                "revision_url": f"{page['fullurl']}?oldid={revision['revid']}",
                "license": LICENSE,
                "license_url": LICENSE_URL,
                "retrieval_method": (
                    "MediaWiki API intro extract; parenthetical transliterations and non-Arabic "
                    "decorative characters removed; first complete Urdu sentence"
                ),
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("assets/source/urdu_wikipedia.json"))
    args = parser.parse_args()
    rows = fetch_sources(args.output)
    print(f"Wrote {len(rows)} revision-pinned source sentences to {args.output}")


if __name__ == "__main__":
    main()
