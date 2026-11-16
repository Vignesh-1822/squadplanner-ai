"""Find photos for the handful of destinations Wikipedia has no image for.

Run rarely and by hand — it is not part of the request path. Wikipedia already covers ~97% of
the dataset; this closes the remainder, which are mostly real regions filed under another title
("Long Island Wine Country" -> Long Island AVA) or articles with no lead photo.

Why a model with web search rather than a plain search API: a bare search for these names is
confidently wrong. Searching "St. John" returns Pope John VI, and "White Mountains" returns a
UFO-abduction article — both with images, both nonsense on a travel card. A model reading the
results can tell which page is actually the place.

Two guardrails do the real work:

  * ``allowed_domains`` restricts results to sources that permit reuse. Without it the best photo
    is usually on someone's travel blog, and embedding that is both hotlinking and infringement.
  * Every URL is verified with a HEAD request before it is kept. Models return plausible image
    URLs that 404, and an unverified one becomes a broken card.

Verified images are downloaded into data/destination_images/ so we host them; Unsplash is the
exception, since their guidelines require their CDN to be hotlinked.

Usage:
    ./venv/bin/python scripts/find_missing_destination_images.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.client import close_client, get_collection  # noqa: E402
from tools.destination_images import (  # noqa: E402
    _COLLECTION,
    _CREDITS_FILE,
    _MANUAL_DIR,
    _USER_AGENT,
)

# Sources whose licensing permits reuse in a commercial product.
ALLOWED_DOMAINS = [
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "en.wikipedia.org",
    "unsplash.com",
    "images.unsplash.com",
    "pexels.com",
    "images.pexels.com",
    "nps.gov",
    "usgs.gov",
]

# Unsplash requires hotlinking, so its results are recorded as URLs instead of downloaded.
HOTLINK_ONLY = ("unsplash.com",)

MODEL = "claude-opus-5"

PROMPT = """Find one photograph of this exact place for a travel app:

  {name}, {state} (United States) — a {type}

Requirements:
- It must be a photo of THIS place. If you cannot confirm the page is about this exact
  location, return null rather than something approximate.
- Return a direct image file URL (ending .jpg/.jpeg/.png/.webp), not a page URL.
- Landscape orientation, suitable as a wide banner.

Reply with ONLY a JSON object, no other text:
{{"image_url": "...", "source": "wikimedia|unsplash|pexels|nps", "credit": "...", "page_url": "..."}}

or exactly {{"image_url": null}} if you cannot find one you are confident about."""


def load_credits() -> dict:
    path = _MANUAL_DIR / _CREDITS_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_credits(credits: dict) -> None:
    (_MANUAL_DIR / _CREDITS_FILE).write_text(
        json.dumps(credits, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class QuotaExhausted(RuntimeError):
    """The account's usage limit is reached — retrying the remaining rows is pointless."""


def ask_model(client, destination: dict) -> dict | None:
    """One web-search-backed lookup. Returns the parsed JSON answer, or None.

    A single bad lookup must not take down the run, so API errors are swallowed per row — with
    the exception of a spent usage limit, which will fail identically for every remaining row.
    """
    import anthropic

    try:
        response = _create(client, destination)
    except anthropic.BadRequestError as exc:
        if "usage limit" in str(exc).lower():
            raise QuotaExhausted(str(exc)) from exc
        print(f"    api error: {str(exc)[:100]}")
        return None
    except anthropic.APIError as exc:
        print(f"    api error: {str(exc)[:100]}")
        return None

    if response.stop_reason == "refusal":
        return None

    text = "".join(block.text for block in response.content if block.type == "text")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _create(client, destination: dict):
    return client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 6,
                "allowed_domains": ALLOWED_DOMAINS,
            }
        ],
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    name=destination["name"],
                    state=destination.get("state", ""),
                    type=destination.get("type", "place"),
                ),
            }
        ],
    )


_COMMONS_FILE = re.compile(r"^https?://commons\.wikimedia\.org/wiki/File:(.+)$", re.I)
_COMMONS_UPLOAD = re.compile(r"^https?://upload\.wikimedia\.org/wikipedia/[^/]+/(?:thumb/)?\w/\w\w/([^/]+)", re.I)


def normalize(url: str) -> str:
    """Rewrite Wikimedia answers to a form that resolves from the filename alone.

    A direct upload.wikimedia.org path embeds an MD5-derived ``/x/xx/`` prefix the model cannot
    know, so it guesses and serves a 404 page. Special:FilePath resolves the real location from
    just the filename, which the model *does* get right — so both the description-page form
    (/wiki/File:Foo.jpg) and the guessed-path form are rewritten through it.
    """
    url = url.strip()
    for pattern in (_COMMONS_FILE, _COMMONS_UPLOAD):
        match = pattern.match(url)
        if match:
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{match.group(1)}"
    return url


async def verify(url: str) -> tuple[bool, str]:
    """A URL is only usable if it actually serves an image. Models invent plausible ones."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
            resp = await http.head(url, headers={"User-Agent": _USER_AGENT})
            if resp.status_code >= 400:  # some CDNs reject HEAD
                resp = await http.get(url, headers={"User-Agent": _USER_AGENT})
            content_type = resp.headers.get("content-type", "")
            return resp.status_code == 200 and content_type.startswith("image/"), content_type
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:60]


async def download(url: str, destination_id: str, content_type: str) -> Path | None:
    extension = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type.split(";")[0].strip())
    if not extension:
        return None
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
            resp = await http.get(url, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
        path = _MANUAL_DIR / f"{destination_id}{extension}"
        path.write_bytes(resp.content)
        return path
    except Exception:  # noqa: BLE001
        return None


async def missing_destinations(limit: int | None) -> list[dict]:
    dataset = {str(d["id"]): d for d in json.loads(
        (Path(__file__).resolve().parent.parent / "data" / "destinations.json").read_text()
    )}
    collection = get_collection(_COLLECTION)
    ids = [
        row["key"].split(":", 1)[1]
        async for row in collection.find({"key": {"$regex": "^destination_image:"}, "image_url": ""})
    ]
    rows = [dataset[i] for i in ids if i in dataset]
    rows.sort(key=lambda d: d["name"])
    return rows[:limit] if limit else rows


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="look up but write nothing")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    from anthropic import Anthropic

    from config import settings

    # The key lives in backend/.env, which the SDK does not read on its own — take it from
    # settings, the same way config.get_llm() does.
    client = Anthropic(api_key=settings.anthropic_api_key)
    targets = await missing_destinations(args.limit)
    print(f"{len(targets)} destinations without a photo\n")

    credits = load_credits()
    found = rejected = 0

    for destination in targets:
        did = str(destination["id"])
        label = f"{destination['name']}, {destination.get('state','')}"
        try:
            answer = await asyncio.to_thread(ask_model, client, destination)
        except QuotaExhausted as exc:
            print(f"\n  Stopped: {exc}")
            print("  Raise the limit in the Anthropic Console, then re-run — finished rows are kept.")
            break

        if not answer or not answer.get("image_url"):
            print(f"  ✗ {label:<40} model found nothing")
            rejected += 1
            continue

        url = normalize(answer["image_url"])
        ok, content_type = await verify(url)
        if not ok:
            print(f"  ✗ {label:<40} unusable ({content_type}) {url[:70]}")
            rejected += 1
            continue

        source = (answer.get("source") or "").lower()
        hotlink = any(domain in url for domain in HOTLINK_ONLY)

        if args.dry_run:
            print(f"  ~ {label:<40} {('hotlink' if hotlink else 'download'):<9} {url[:60]}")
            found += 1
            continue

        entry = {
            "credit": answer.get("credit", ""),
            "source": source or "manual",
            "link": answer.get("page_url", ""),
        }
        if hotlink:
            entry["url"] = url  # their guidelines require serving from their CDN
            print(f"  ✓ {label:<40} hotlinked  {url[:56]}")
        else:
            path = await download(url, did, content_type)
            if not path:
                print(f"  ✗ {label:<40} download failed")
                rejected += 1
                continue
            print(f"  ✓ {label:<40} saved      {path.name} ({path.stat().st_size // 1024} KB)")

        credits[did] = entry
        found += 1

    if not args.dry_run and credits:
        save_credits(credits)

    print(f"\nfound {found}, still missing {rejected}")
    if not args.dry_run:
        print("Review the images, delete any you dislike, then commit the folder.")
    close_client()


if __name__ == "__main__":
    asyncio.run(main())
