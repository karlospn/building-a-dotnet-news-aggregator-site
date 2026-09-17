import glob
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
from dateutil import parser as dateparser

from common import (
    canonicalize_url,
    content_id,
    convert_rss_data_to_md,
    enrich_item,
    existing_urls,
    extract_entry_image,
    parse_yml_files,
    record_feed_health,
    select_featured,
)
from youtube import is_youtube_channel


CONTENT_ROOT = Path("site/dotnetramblings/content/post")


def _entry_date(entry):
    raw_date = entry.get("published") or entry.get("updated")
    if not raw_date:
        return None
    parsed = dateparser.parse(raw_date)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_rss_data(source, now=None):
    now = now or datetime.now(timezone.utc)
    earliest = now - timedelta(hours=36)
    feed = feedparser.parse(source["feed"])
    if feed.bozo and not feed.entries:
        raise ValueError(str(feed.bozo_exception))

    items = []
    for entry in feed.entries:
        published = _entry_date(entry)
        if not published or published < earliest or published > now + timedelta(hours=2):
            continue

        url = entry.get("link")
        title = entry.get("title")
        if not url or not title:
            continue

        item = {
            "title": title,
            "url": url,
            "date": published.isoformat(),
            "summary": entry.get("summary") or entry.get("description") or "",
            "content": (
                entry.get("content", [{}])[0].get("value", "")
                if entry.get("content")
                else ""
            ),
            "website": source["website"],
            "source_id": source["id"],
            "source_title": source["title"],
            "source_description": source["description"],
            "author": entry.get("author") or source["author"],
            "content_type": "article",
            "image": extract_entry_image(entry, url),
        }
        items.append(enrich_item(item))

    record_feed_health(source, "healthy", len(items))
    return items


def fetch_rss_feeds(sources):
    items = []
    seen_urls = existing_urls(CONTENT_ROOT)
    seen_titles = set()
    attempted = 0
    succeeded = 0
    for source in sources:
        if is_youtube_channel(source["feed"]):
            continue
        attempted += 1
        try:
            for item in get_rss_data(source):
                normalized_title = re.sub(r"\W+", "", item["title"].lower())
                canonical_url = canonicalize_url(item["url"])
                if canonical_url in seen_urls or normalized_title in seen_titles:
                    continue
                seen_urls.add(canonical_url)
                seen_titles.add(normalized_title)
                items.append(item)
            succeeded += 1
        except Exception as error:
            record_feed_health(source, "error", message=str(error))
            print(f"Failed to parse feed {source['feed']}: {error}")

    if attempted and not succeeded:
        raise RuntimeError("All RSS feeds failed; no content was generated")
    items.sort(key=lambda value: value["date"], reverse=True)
    return select_featured(items)


def generate_hugo_content(items):
    for item in items:
        published = dateparser.parse(item["date"]).astimezone(timezone.utc)
        directory = CONTENT_ROOT / published.strftime("%d_%m_%Y")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{content_id(item['canonical_url'])}.md"
        path.write_text(convert_rss_data_to_md(item), encoding="utf-8")


def main():
    file_paths = glob.glob(os.path.join("./data", "*.yml"))
    sources = parse_yml_files(file_paths)
    generate_hugo_content(fetch_rss_feeds(sources))


if __name__ == "__main__":
    main()
