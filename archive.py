import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dateutil import parser as dateparser

from common import (
    canonicalize_url,
    classify_ai_subtopics,
    deduplicate_video_items,
    fallback_thumbnail,
    normalize_title,
)


ARCHIVE_PATH = Path("site/dotnetramblings/static/archive.json")
CONTENT_ROOTS = (
    Path("site/dotnetramblings/content/post"),
    Path("site/dotnetramblings/content/videos"),
)


def read_content_item(path):
    text = path.read_text(encoding="utf-8")
    _, front_matter, body = text.split("---", 2)
    metadata = yaml.safe_load(front_matter)
    summary = body.strip().split("\n\n- ", 1)[0].strip()
    return {
        "title": normalize_title(metadata["title"]),
        "date": _date_string(metadata["date"]),
        "link": canonicalize_url(metadata["canonicalUrl"]),
        "source": metadata["source"],
        "sourceId": metadata["sourceId"],
        "sourceUrl": metadata.get("sourceUrl", ""),
        "author": metadata.get("author", ""),
        "contentType": metadata["contentType"],
        "topics": metadata["topics"],
        "aiSubtopics": metadata.get("aiSubtopics")
        or (
            classify_ai_subtopics(metadata["title"], summary)
            if "AI" in metadata["topics"]
            else []
        ),
        "thumbnail": metadata["thumbnail"],
        "fallbackThumbnail": metadata.get("fallbackThumbnail")
        or fallback_thumbnail(metadata["topics"], metadata["contentType"]),
        "readingMinutes": metadata.get("readingMinutes"),
        "duration": metadata.get("duration", ""),
        "rank": metadata.get("rank", 0),
        "whyItMatters": metadata.get("whyItMatters", ""),
        "summary": summary,
    }


def build_archive(now=None, retention_days=180):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    entries = {}

    if ARCHIVE_PATH.exists():
        for item in json.loads(ARCHIVE_PATH.read_text(encoding="utf-8")):
            item["title"] = normalize_title(item.get("title", ""))
            item["aiSubtopics"] = item.get("aiSubtopics") or (
                classify_ai_subtopics(item["title"], item.get("summary", ""))
                if "AI" in item.get("topics", [])
                else []
            )
            item["fallbackThumbnail"] = item.get("fallbackThumbnail") or fallback_thumbnail(
                item.get("topics") or ["General"],
                item.get("contentType", "article"),
            )
            entries[canonicalize_url(item["link"])] = item

    for root in CONTENT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            item = read_content_item(path)
            entries[item["link"]] = item

    retained = []
    for item in entries.values():
        published = dateparser.parse(item["date"])
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published.astimezone(timezone.utc) >= cutoff:
            retained.append(item)

    retained.sort(key=lambda item: item["date"], reverse=True)
    articles = [item for item in retained if item.get("contentType") != "video"]
    videos = deduplicate_video_items(
        [item for item in retained if item.get("contentType") == "video"]
    )
    retained = sorted(articles + videos, key=lambda item: item["date"], reverse=True)
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ARCHIVE_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(retained, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary_path.replace(ARCHIVE_PATH)
    return len(retained)


def _date_string(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


if __name__ == "__main__":
    print(f"Archived {build_archive()} content items")
