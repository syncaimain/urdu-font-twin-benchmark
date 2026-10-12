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
CANDIDATE_TITLES = [
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
    "لاہور",
    "کوئٹہ",
    "ملتان",
    "فیصل آباد",
    "راولپنڈی",
    "گوجرانوالہ",
    "سیالکوٹ",
    "سکھر",
    "ایبٹ آباد",
    "مردان",
    "خیبر پختونخوا",
    "پنجاب، پاکستان",
    "سندھ",
    "بلوچستان، پاکستان",
    "گلگت بلتستان",
    "آزاد کشمیر",
    "دریائے جہلم",
    "دریائے چناب",
    "دریائے راوی",
    "دریائے ستلج",
    "ہمالیہ",
    "ہندوکش",
    "بحیرہ عرب",
    "بحر ہند",
    "چاند",
    "سورج",
    "عطارد",
    "زہرہ",
    "مریخ",
    "مشتری",
    "زحل",
    "فلکیات",
    "طبیعیات",
    "کیمیا",
    "حیاتیات",
    "ریاضی",
    "طب",
    "انجینئری",
    "انٹرنیٹ",
    "مصنوعی ذہانت",
    "روبوٹ",
    "موبائل فون",
    "ریڈیو",
    "ٹیلی ویژن",
    "اخبار",
    "ادب",
    "شاعری",
    "ناول",
    "مرزا غالب",
    "علامہ اقبال",
    "فیض احمد فیض",
    "محمد علی جناح",
    "لیاقت علی خان",
    "فاطمہ جناح",
    "عبدالستار ایدھی",
    "سر سید احمد خان",
    "کرکٹ",
    "ہاکی",
    "فٹ بال",
    "موسیقی",
    "زراعت",
    "معیشت",
    "تجارت",
    "جمہوریت",
    "آئین",
    "پارلیمان",
    "اقوام متحدہ",
    "افغانستان",
    "بھارت",
    "ایران",
    "چین",
    "ترکی",
    "سعودی عرب",
    "بنگلہ دیش",
    "نیپال",
    "سری لنکا",
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


def _chunks(items: list[str], size: int = 20):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _fetch_batch(titles: list[str]) -> list[tuple[str, dict | None]]:
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
        "titles": "|".join(titles),
    }
    request = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "UrduFontTwinBenchmark/0.2 (research benchmark)"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        query = json.load(response)["query"]

    aliases = {
        item["from"]: item["to"]
        for group in (query.get("normalized", []), query.get("redirects", []))
        for item in group
    }
    pages = {page["title"]: page for page in query["pages"]}
    resolved = []
    for requested in titles:
        title = requested
        visited = set()
        while title in aliases and title not in visited:
            visited.add(title)
            title = aliases[title]
        resolved.append((requested, pages.get(title)))
    return resolved


def fetch_sources(output: Path, limit: int = 60, titles: list[str] | None = None) -> list[dict]:
    candidates = list(titles or CANDIDATE_TITLES)
    if limit < 1:
        raise ValueError("Source limit must be positive")
    if limit > len(candidates):
        raise ValueError(f"Requested {limit} items from only {len(candidates)} candidates")

    rows: list[dict] = []
    skipped: list[str] = []
    seen_pages: set[int] = set()
    fetched = [item for batch in _chunks(candidates) for item in _fetch_batch(batch)]
    for requested_title, page in fetched:
        if len(rows) >= limit:
            break
        if not page or page.get("missing") or "revisions" not in page:
            skipped.append(f"{requested_title}: missing")
            continue
        revision = page["revisions"][0]
        sentence = _first_sentence(page.get("extract", ""))
        if len(sentence.split()) < 3:
            skipped.append(f"{requested_title}: no usable sentence")
            continue
        page_key = int(page.get("pageid") or revision["revid"])
        if page_key in seen_pages:
            skipped.append(f"{requested_title}: duplicate resolved page")
            continue
        seen_pages.add(page_key)
        index = len(rows) + 1
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
                "selection_rank": index,
            }
        )

    if len(rows) < limit:
        raise RuntimeError(
            f"Only {len(rows)} usable unique sources were found for a target of {limit}. "
            f"Skipped: {'; '.join(skipped)}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if skipped:
        print(f"Skipped {len(skipped)} unusable or duplicate candidates")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("assets/full/source/urdu_wikipedia.json"))
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()
    rows = fetch_sources(args.output, limit=args.limit)
    print(f"Wrote {len(rows)} revision-pinned source sentences to {args.output}")


if __name__ == "__main__":
    main()
