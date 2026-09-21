import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import yaml
from bs4 import BeautifulSoup


SITE_ROOT = Path("site/dotnetramblings")
HEALTH_FILE = SITE_ROOT / "data/feed_health.json"
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}
AI_SUBTOPIC_KEYWORDS = {
    "Agents": (
        "agent",
        "agentic",
        "multi-agent",
        "multi agent",
        "deep agent",
        "super agent",
    ),
    "RAG": (
        "rag",
        "retrieval augmented",
        "retrieval-augmented",
        "vector search",
        "vector store",
        "embedding",
        "knowledge base",
    ),
    "MCP": ("mcp", "model context protocol"),
    "Local Models": (
        "local model",
        "local llm",
        "ollama",
        "onnx",
        "llama.cpp",
        "quantization",
    ),
    "Copilot": ("copilot", "github models", "coding agent"),
    "SDKs": (
        "sdk",
        "api",
        "semantic kernel",
        "agent framework",
        "microsoft.extensions.ai",
    ),
    "Security": (
        "prompt injection",
        "jailbreak",
        "guardrail",
        "poisoning",
        "pii",
        "red team",
        "security",
        "secure ai",
    ),
    "Evaluation": (
        "evaluate",
        "evaluating",
        "evaluation",
        "evals",
        "benchmark",
        "observability",
        "monitoring",
        "tracing",
    ),
}


def parse_yml_files(file_paths):
    sources = []
    for file_path in file_paths:
        with open(file_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        if not all(field in data for field in ("Feed", "Title", "Website")):
            print(f"Missing basic data. Skipped {file_path}.")
            continue

        feed_url = _ensure_url_scheme(str(data["Feed"]).strip())
        website_url = _ensure_url_scheme(str(data["Website"]).strip())
        sources.append(
            {
                "id": Path(file_path).stem,
                "feed": feed_url,
                "title": str(data["Title"]).strip(),
                "website": website_url,
                "description": data.get("Description", ""),
                "author": data.get("Author", ""),
            }
        )
    return sources


def canonicalize_url(url):
    parsed = urlparse(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            urlencode(query),
            "",
        )
    )


def content_id(url):
    return hashlib.sha1(canonicalize_url(url).encode("utf-8")).hexdigest()[:12]


def sanitize_html(value):
    soup = BeautifulSoup(value or "", "html.parser")
    return _sanitize_text(" ".join(soup.get_text(" ", strip=True).split()))


def summarize(value, limit=420):
    text = sanitize_html(value)
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0]
    return f"{shortened}…"


def extract_entry_image(entry, article_url):
    for attribute in ("media_content", "media_thumbnail"):
        for image in entry.get(attribute, []):
            candidate = _valid_image_url(
                image.get("url", ""),
                article_url,
                image.get("width"),
                image.get("height"),
            )
            if candidate:
                return candidate

    for link in entry.get("links", []):
        if str(link.get("type", "")).startswith("image/") and link.get("href"):
            candidate = _valid_image_url(link["href"], article_url)
            if candidate:
                return candidate

    summary_image = BeautifulSoup(
        entry.get("summary") or entry.get("description") or "", "html.parser"
    ).find("img")
    if summary_image and summary_image.get("src"):
        candidate = _valid_image_url(
            summary_image["src"],
            article_url,
            summary_image.get("width"),
            summary_image.get("height"),
        )
        if candidate:
            return candidate

    return _extract_open_graph_image(article_url)


def enrich_item(item):
    title = normalize_title(item["title"])
    summary = summarize(item.get("summary", ""))
    title_topics = classify_topics(title, include_general=False)
    contextual_topics = classify_topics(
        " ".join((summary, item.get("source_title", ""), item.get("source_description", ""))),
        include_general=False,
    )
    topics = list(dict.fromkeys(title_topics + contextual_topics))[:3] or ["General"]
    ai_subtopics = classify_ai_subtopics(title, summary) if "AI" in topics else []
    fallback_image = fallback_thumbnail(topics, item.get("content_type", "article"))
    image = item.get("image") or fallback_image
    full_content = sanitize_html(item.get("content", ""))
    reading_minutes = (
        max(1, round(len(full_content.split()) / 220))
        if len(full_content.split()) >= 150
        else 0
    )
    rank = 50 + min(len(summary) // 80, 5) + min(len(topics) * 2, 8)
    if image and image != "images/misc.png":
        rank += 8
    if item.get("content_type") == "video":
        rank += 2

    item.update(
        {
            "canonical_url": canonicalize_url(item["url"]),
            "title": title,
            "summary": summary,
            "topics": topics,
            "ai_subtopics": ai_subtopics,
            "thumbnail": image,
            "fallback_thumbnail": fallback_image,
            "reading_minutes": reading_minutes,
            "rank": rank,
            "why_it_matters": _why_it_matters(topics, item.get("content_type", "article")),
        }
    )
    return item


def select_featured(items, limit=6):
    selected = 0
    used_sources = set()
    for item in sorted(items, key=lambda value: (value["rank"], value["date"]), reverse=True):
        source_id = item["source_id"]
        if source_id in used_sources:
            continue
        item["featured"] = True
        used_sources.add(source_id)
        selected += 1
        if selected == limit:
            break
    return items


def convert_rss_data_to_md(item):
    front_matter = {
        "title": item["title"],
        "date": item["date"],
        "link": item["canonical_url"],
        "canonicalUrl": item["canonical_url"],
        "source": item["source_title"],
        "sourceId": item["source_id"],
        "sourceUrl": item["website"],
        "author": item.get("author") or None,
        "contentType": item.get("content_type", "article"),
        "topics": list(item["topics"]),
        "tags": list(item["topics"]),
        "aiSubtopics": list(item.get("ai_subtopics", [])) or None,
        "thumbnail": item["thumbnail"],
        "fallbackThumbnail": item["fallback_thumbnail"],
        "readingMinutes": item.get("reading_minutes") or None,
        "duration": item.get("duration") or None,
        "rank": item["rank"],
        "featured": item.get("featured", False),
        "whyItMatters": item["why_it_matters"],
        "showShare": False,
        "showReadTime": False,
    }
    front_matter = {key: value for key, value in front_matter.items() if value not in (None, "")}
    yaml_front_matter = yaml.safe_dump(
        front_matter,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    ).strip()
    return (
        f"---\n{yaml_front_matter}\n---\n"
        f"{item['summary']}\n\n"
        f"- {item['why_it_matters']}\n"
        f"- Link to {item.get('content_type', 'article')}: {item['canonical_url']}"
    )


def classify_topics(text, include_general=True):
    normalized = text.lower()
    with open("config/thumbnail_config.yml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    topics = []
    for item in config["keywords"]:
        if any(_keyword_matches(keyword, normalized) for keyword in item["keywords"]):
            topic = item.get("topic", "General")
            if topic not in topics:
                topics.append(topic)
    return topics[:3] or (["General"] if include_general else [])


def classify_ai_subtopics(title, summary=""):
    title_text = normalize_title(title).casefold()
    summary_text = sanitize_html(summary).casefold()
    matches = []
    for subtopic, keywords in AI_SUBTOPIC_KEYWORDS.items():
        if any(
            _keyword_matches(keyword, title_text)
            or _keyword_matches(keyword, summary_text)
            for keyword in keywords
        ):
            matches.append(subtopic)
    return matches


def existing_urls(content_root):
    urls = set()
    root = Path(content_root)
    if not root.exists():
        return urls
    for markdown_file in root.rglob("*.md"):
        text = markdown_file.read_text(encoding="utf-8")
        match = re.search(r"^(?:canonicalUrl|link):\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
        if match:
            urls.add(canonicalize_url(match.group(1)))
    return urls


def existing_title_dates(content_root):
    titles = {}
    root = Path(content_root)
    if not root.exists():
        return titles
    for markdown_file in root.rglob("*.md"):
        try:
            text = markdown_file.read_text(encoding="utf-8")
            _, front_matter, _ = text.split("---", 2)
            metadata = yaml.safe_load(front_matter)
            key = normalize_title_key(metadata.get("title", ""))
            date = _parse_datetime(metadata.get("date"))
            if key and date:
                titles.setdefault(key, []).append(date)
        except (OSError, ValueError, yaml.YAMLError):
            continue
    return titles


def is_recent_title_duplicate(title, published, known_titles, within_days=7):
    key = normalize_title_key(title)
    published_at = _parse_datetime(published)
    if not key or not published_at:
        return False
    threshold = timedelta(days=within_days)
    if any(abs(published_at - existing) <= threshold for existing in known_titles.get(key, [])):
        return True
    known_titles.setdefault(key, []).append(published_at)
    return False


def deduplicate_video_items(items, within_days=7):
    known_titles = {}
    deduplicated = []
    ordered = sorted(
        items,
        key=lambda item: _parse_datetime(item.get("date"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for item in ordered:
        if is_recent_title_duplicate(
            item.get("title", ""),
            item.get("date"),
            known_titles,
            within_days,
        ):
            continue
        deduplicated.append(item)
    return deduplicated


def remove_duplicate_title_files(content_root, within_days=7):
    records = []
    root = Path(content_root)
    if not root.exists():
        return 0
    for path in root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
            _, front_matter, _ = text.split("---", 2)
            metadata = yaml.safe_load(front_matter)
            published = _parse_datetime(metadata.get("date"))
            if published:
                records.append((published, path, metadata.get("title", "")))
        except (OSError, ValueError, yaml.YAMLError):
            continue
    records.sort(key=lambda record: record[0], reverse=True)

    known_titles = {}
    removed = 0
    for published, path, title in records:
        if is_recent_title_duplicate(
            title,
            published,
            known_titles,
            within_days,
        ):
            path.unlink()
            removed += 1
    return removed


def normalize_title(value):
    text = str(value or "")
    for _ in range(2):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = unicodedata.normalize("NFKC", text)
    return _sanitize_text(" ".join(text.split()))


def normalize_title_key(value):
    title = normalize_title(value).casefold()
    return re.sub(r"[\W_]+", "", title, flags=re.UNICODE)


def record_feed_health(source, status, item_count=0, message=""):
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    health = {}
    if HEALTH_FILE.exists():
        health = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
    current = health.get(source["id"], {})
    new_state = {
        "status": status,
        "itemCount": item_count,
        "message": message[:160],
    }
    if all(current.get(key) == value for key, value in new_state.items()):
        return False
    health[source["id"]] = {
        **new_state,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }
    HEALTH_FILE.write_text(json.dumps(health, indent=2, sort_keys=True), encoding="utf-8")
    return True


def clean_content(content_root, retention_days=8, now=None):
    now = now or datetime.now()
    cutoff = now - timedelta(days=retention_days)
    root = Path(content_root)
    if not root.exists():
        return 0

    removed = 0
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        try:
            directory_date = datetime.strptime(directory.name, "%d_%m_%Y")
        except ValueError:
            continue
        if directory_date >= cutoff:
            continue
        for file in directory.iterdir():
            if file.is_file():
                file.unlink()
        directory.rmdir()
        removed += 1
    return removed


def _extract_open_graph_image(url):
    try:
        request = Request(url, headers={"User-Agent": "DotNetRamblings/1.0"})
        with urlopen(request, timeout=5) as response:
            html = response.read(300_000)
        soup = BeautifulSoup(html, "html.parser")
        image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        return _valid_image_url(image.get("content", ""), url) if image else ""
    except Exception:
        return ""


def fallback_thumbnail(topics, content_type="article"):
    if content_type == "video":
        return "images/youtube.png"
    with open("config/thumbnail_config.yml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    for item in config["keywords"]:
        if item.get("topic") in topics:
            return item["image"]
    return config["default_image"]


def _valid_image_url(value, base_url="", width=None, height=None):
    if not value:
        return ""
    try:
        if width and int(width) <= 16:
            return ""
        if height and int(height) <= 16:
            return ""
    except (TypeError, ValueError):
        pass

    candidate = urljoin(base_url, str(value).strip())
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.lower()
    if any(marker in path for marker in ("/pixel", "tracking", "spacer", "1x1")):
        return ""
    return candidate


def _why_it_matters(topics, content_type):
    subject = " and ".join(topics[:2])
    action = "watch" if content_type == "video" else "read"
    return f"Worth a {action} for developers following {subject}."


def _sanitize_text(text):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", str(text)).strip()


def _parse_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ensure_url_scheme(url):
    return url if urlparse(url).scheme else f"https://{url}"


def _keyword_matches(keyword, text):
    keyword = keyword.lower()
    if keyword.isalnum() and len(keyword) <= 3:
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text
