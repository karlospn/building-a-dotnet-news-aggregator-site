import glob
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yaml

from common import canonicalize_url, convert_rss_data_to_md, enrich_item, parse_yml_files
from youtube import is_youtube_channel


def website_key(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def load_markdown(path):
    text = path.read_text(encoding="utf-8")
    _, front_matter, body = text.split("---", 2)
    metadata = yaml.safe_load(front_matter)
    summary = body.strip().split("\n\n- ", 1)[0].strip()
    return metadata, summary


def find_source(metadata, sources, content_type):
    candidates = [
        source
        for source in sources
        if is_youtube_channel(source["feed"]) == (content_type == "video")
    ]
    source_id = metadata.get("sourceId")
    if source_id:
        for source in candidates:
            if source["id"] == source_id:
                return source
    legacy_tags = metadata.get("tags") or []
    legacy_source = legacy_tags[0] if legacy_tags else ""
    link_host = urlparse(metadata.get("link", "")).netloc.lower().removeprefix("www.")
    for source in candidates:
        if website_key(source["website"]) == legacy_source:
            return source
    for source in candidates:
        if website_key(source["website"]).startswith(legacy_source) and legacy_source:
            return source
    for source in candidates:
        if link_host and link_host == urlparse(source["website"]).netloc.lower().removeprefix("www."):
            return source
    return {
        "id": legacy_source.replace("/", "-") or "unknown",
        "title": legacy_source or link_host or "Unknown source",
        "website": metadata.get("link", ""),
        "description": "",
        "author": "",
    }


def original_metadata(path):
    relative_path = path.as_posix()
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    try:
        _, front_matter, _ = result.stdout.split("---", 2)
        return yaml.safe_load(front_matter)
    except (ValueError, yaml.YAMLError):
        return None


def main():
    sources = parse_yml_files(glob.glob(os.path.join("./data", "*.yml")))
    roots = (
        (Path("site/dotnetramblings/content/post"), "article"),
        (Path("site/dotnetramblings/content/videos"), "video"),
    )
    migrated = 0
    for root, content_type in roots:
        for path in root.rglob("*.md"):
            metadata, summary = load_markdown(path)
            source = find_source(original_metadata(path) or metadata, sources, content_type)
            date = metadata["date"]
            if hasattr(date, "isoformat"):
                date = date.isoformat()
            image = metadata.get("thumbnail", "")
            if content_type == "video":
                video_id = urlparse(metadata["link"]).query.removeprefix("v=")
                if video_id:
                    image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            item = enrich_item(
                {
                    "title": metadata["title"],
                    "url": canonicalize_url(metadata["link"]),
                    "date": date,
                    "summary": summary,
                    "website": source["website"],
                    "source_id": source["id"],
                    "source_title": source["title"],
                    "source_description": source["description"],
                    "author": source["author"],
                    "content_type": content_type,
                    "image": image,
                }
            )
            path.write_text(convert_rss_data_to_md(item), encoding="utf-8")
            migrated += 1
    print(f"Migrated {migrated} content files")


if __name__ == "__main__":
    main()
