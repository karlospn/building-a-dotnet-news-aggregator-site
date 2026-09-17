import glob
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from googleapiclient.discovery import build

from common import (
    canonicalize_url,
    content_id,
    convert_rss_data_to_md,
    enrich_item,
    existing_urls,
    parse_yml_files,
    record_feed_health,
    select_featured,
)


CONTENT_ROOT = Path("site/dotnetramblings/content/videos")


def get_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is required")
    return build("youtube", "v3", developerKey=api_key)


def is_youtube_channel(url):
    if "://" not in url:
        url = f"https://{url}"
    return urlparse(url).netloc.lower() in {"www.youtube.com", "youtube.com"}


def get_channel_id(url, youtube):
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not is_youtube_channel(url) or not parts:
        return None
    if parts[0] == "channel" and len(parts) > 1:
        return parts[1]
    if parts[0] == "user" and len(parts) > 1:
        response = youtube.channels().list(part="id", forUsername=parts[1]).execute()
        return response["items"][0]["id"] if response.get("items") else None
    if parts[0].startswith("@"):
        response = youtube.channels().list(
            part="id", forHandle=unquote(parts[0][1:])
        ).execute()
        return response["items"][0]["id"] if response.get("items") else None
    return None


def _format_duration(value):
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return ""
    hours, minutes, seconds = [int(part or 0) for part in match.groups()]
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def get_youtube_data(source, youtube=None, now=None):
    youtube = youtube or get_youtube_client()
    now = now or datetime.now(timezone.utc)
    channel_id = get_channel_id(source["feed"], youtube)
    if not channel_id:
        raise ValueError("YouTube channel URL could not be resolved")

    response = youtube.search().list(
        part="snippet", channelId=channel_id, type="video", order="date", maxResults=25
    ).execute()
    recent = []
    for video in response.get("items", []):
        published = datetime.strptime(
            video["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        if published >= now - timedelta(hours=48) and published <= now + timedelta(hours=2):
            recent.append(video)

    ids = [video["id"]["videoId"] for video in recent]
    durations = {}
    if ids:
        details = youtube.videos().list(part="contentDetails", id=",".join(ids)).execute()
        durations = {
            item["id"]: _format_duration(item["contentDetails"].get("duration"))
            for item in details.get("items", [])
        }

    items = []
    for video in recent:
        snippet = video["snippet"]
        video_id = video["id"]["videoId"]
        thumbnail = (
            snippet.get("thumbnails", {}).get("high")
            or snippet.get("thumbnails", {}).get("medium")
            or {}
        ).get("url", "")
        item = {
            "title": snippet["title"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "date": snippet["publishedAt"],
            "summary": snippet.get("description", ""),
            "website": source["website"],
            "source_id": source["id"],
            "source_title": source["title"],
            "source_description": source["description"],
            "author": source["author"],
            "content_type": "video",
            "image": thumbnail,
            "duration": durations.get(video_id, ""),
        }
        items.append(enrich_item(item))

    record_feed_health(source, "healthy", len(items))
    return items


def fetch_youtube_channels(sources):
    items = []
    seen_urls = existing_urls(CONTENT_ROOT)
    youtube = get_youtube_client()
    attempted = 0
    succeeded = 0
    for source in sources:
        if not is_youtube_channel(source["feed"]):
            continue
        attempted += 1
        try:
            for item in get_youtube_data(source, youtube):
                if item["canonical_url"] in seen_urls:
                    continue
                seen_urls.add(item["canonical_url"])
                items.append(item)
            succeeded += 1
            time.sleep(0.25)
        except Exception as error:
            record_feed_health(source, "error", message=str(error))
            print(f"Failed to parse channel {source['feed']}: {error}")
    if attempted and not succeeded:
        raise RuntimeError("All YouTube channels failed; no content was generated")
    items.sort(key=lambda value: value["date"], reverse=True)
    return select_featured(items)


def generate_hugo_content(items):
    for item in items:
        published = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
        directory = CONTENT_ROOT / published.strftime("%d_%m_%Y")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{content_id(item['canonical_url'])}.md"
        path.write_text(convert_rss_data_to_md(item), encoding="utf-8")


def main():
    file_paths = glob.glob(os.path.join("./data", "*.yml"))
    generate_hugo_content(fetch_youtube_channels(parse_yml_files(file_paths)))


if __name__ == "__main__":
    main()
