import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import feedparser
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from common import canonicalize_url, classify_topics, sanitize_html


CONFIG_PATH = Path("config/community_pulse_sources.yml")
OUTPUT_PATH = Path("site/dotnetramblings/data/community_pulse.json")
ARCHIVE_PATH = Path("site/dotnetramblings/static/archive.json")
BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
SOCIAL_HOSTS = {
    "bsky.app",
    "public.api.bsky.app",
    "dotnet.social",
    "hachyderm.io",
    "mastodon.social",
    "fosstodon.org",
}


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not config.get("identities"):
        raise ValueError("Community Pulse configuration must contain identities")
    return config


def fetch_bluesky(handle):
    url = (
        f"{BLUESKY_API}?actor={quote(handle)}"
        "&filter=posts_no_replies&limit=30"
    )
    request = Request(url, headers={"User-Agent": "DotNetRamblings/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_mastodon(feed_url):
    parsed = feedparser.parse(
        feed_url,
        request_headers={"User-Agent": "DotNetRamblings/1.0"},
    )
    if parsed.bozo and not parsed.entries:
        raise ValueError(str(parsed.bozo_exception))
    return parsed


def parse_bluesky(payload, identity, account):
    items = []
    for entry in payload.get("feed", []):
        if entry.get("reason"):
            continue
        post = entry.get("post", {})
        record = post.get("record", {})
        if record.get("reply"):
            continue
        text = sanitize_html(record.get("text", ""))
        urls = []
        embed = post.get("embed") or record.get("embed") or {}
        external = embed.get("external") or {}
        if external.get("uri"):
            urls.append(external["uri"])
        for facet in record.get("facets", []):
            for feature in facet.get("features", []):
                if feature.get("$type") == "app.bsky.richtext.facet#link":
                    urls.append(feature.get("uri", ""))
        external_urls = _external_urls(urls)
        if not external_urls:
            continue
        uri = post.get("uri", "")
        rkey = uri.rsplit("/", 1)[-1] if uri else ""
        items.append(
            _item(
                identity,
                platform="bluesky",
                handle=account["handle"],
                published=record.get("createdAt") or post.get("indexedAt"),
                text=text,
                post_url=f"https://bsky.app/profile/{account['handle']}/post/{rkey}",
                external_url=_best_external_url(external_urls),
            )
        )
    return [item for item in items if item]


def parse_mastodon(parsed, identity, account):
    items = []
    for entry in parsed.entries:
        content = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
        soup = BeautifulSoup(content, "html.parser")
        text = sanitize_html(content)
        if text.casefold().startswith("re:"):
            continue
        post_url = entry.get("link", "")
        external_urls = _external_urls(
            [
                anchor.get("href", "")
                for anchor in soup.find_all("a")
                if not {"mention", "hashtag"}.intersection(anchor.get("class", []))
            ],
            excluded_host=urlparse(post_url).netloc.lower(),
        )
        if not external_urls:
            continue
        items.append(
            _item(
                identity,
                platform="mastodon",
                handle=parsed.feed.get("title", identity["name"]),
                published=entry.get("published") or entry.get("updated"),
                text=text,
                post_url=post_url,
                external_url=_best_external_url(external_urls),
            )
        )
    return [item for item in items if item]


def collect(config, now=None, bluesky_fetcher=fetch_bluesky, mastodon_fetcher=fetch_mastodon):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(config.get("retention_days", 7)))
    candidates = []
    successful_accounts = 0
    attempted_accounts = 0

    for identity in config["identities"]:
        for account in identity.get("accounts", []):
            attempted_accounts += 1
            try:
                if account["platform"] == "bluesky":
                    payload = bluesky_fetcher(account["handle"])
                    candidates.extend(parse_bluesky(payload, identity, account))
                elif account["platform"] == "mastodon":
                    parsed = mastodon_fetcher(account["feed"])
                    candidates.extend(parse_mastodon(parsed, identity, account))
                else:
                    raise ValueError(f"Unsupported social platform: {account['platform']}")
                successful_accounts += 1
            except Exception as error:
                print(
                    f"Failed to fetch {identity['name']} "
                    f"from {account.get('platform')}: {error}"
                )

    if attempted_accounts and not successful_accounts:
        raise RuntimeError("All Community Pulse sources failed")

    candidates.extend(_existing_items(cutoff))
    excluded_links = _archive_links() if config.get("exclude_existing_article_links") else set()
    retained = [
        item
        for item in candidates
        if _published_at(item) >= cutoff
        and _is_relevant(item, config.get("include_keywords", []))
        and canonicalize_url(item["externalUrl"]) not in excluded_links
    ]
    return deduplicate_and_cap(
        retained,
        int(config.get("max_posts_per_identity_per_day", 2)),
    )


def deduplicate_and_cap(items, max_per_day=2):
    ordered = sorted(items, key=_published_at, reverse=True)
    seen_ids = set()
    seen_urls = set()
    seen_text = set()
    daily_counts = defaultdict(int)
    result = []
    for item in ordered:
        external_url = canonicalize_url(item["externalUrl"])
        text_key = _text_key(item["excerpt"])
        day_key = (item["identityId"], _published_at(item).date().isoformat())
        if (
            item["id"] in seen_ids
            or external_url in seen_urls
            or (text_key and text_key in seen_text)
            or daily_counts[day_key] >= max_per_day
        ):
            continue
        seen_ids.add(item["id"])
        seen_urls.add(external_url)
        if text_key:
            seen_text.add(text_key)
        daily_counts[day_key] += 1
        item["externalUrl"] = external_url
        result.append(item)
    return result


def write_items(items, path=OUTPUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _item(identity, platform, handle, published, text, post_url, external_url):
    if not published or not post_url or not external_url:
        return None
    published_at = dateparser.parse(str(published))
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    excerpt = text if len(text) <= 280 else f"{text[:281].rsplit(' ', 1)[0]}…"
    topics = classify_topics(
        f"{text} {' '.join(identity.get('default_topics', []))}"
    )
    identifier = hashlib.sha1(post_url.encode("utf-8")).hexdigest()[:16]
    return {
        "id": identifier,
        "identityId": identity["id"],
        "author": identity["name"],
        "handle": handle,
        "platform": platform,
        "publishedAt": published_at.astimezone(timezone.utc).isoformat(),
        "excerpt": excerpt,
        "postUrl": post_url,
        "externalUrl": external_url,
        "topics": topics,
    }


def _external_urls(urls, excluded_host=""):
    result = []
    for value in urls:
        if not value:
            continue
        parsed = urlparse(value)
        host = parsed.netloc.lower()
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or host == excluded_host
            or host in SOCIAL_HOSTS
            or host.endswith(".brid.gy")
        ):
            continue
        canonical = canonicalize_url(value)
        if canonical not in result:
            result.append(canonical)
    return result


def _existing_items(cutoff):
    if not OUTPUT_PATH.exists():
        return []
    return [
        item
        for item in json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if _published_at(item) >= cutoff
    ]


def _archive_links():
    if not ARCHIVE_PATH.exists():
        return set()
    return {
        canonicalize_url(item["link"])
        for item in json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    }


def _published_at(item):
    parsed = dateparser.parse(item["publishedAt"])
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _text_key(text):
    without_urls = re.sub(
        r"(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?",
        "",
        text.casefold(),
    )
    return re.sub(r"[\W_]+", "", without_urls, flags=re.UNICODE)


def _is_relevant(item, keywords):
    haystack = f"{item.get('excerpt', '')} {item.get('externalUrl', '')}".casefold()
    for keyword in keywords:
        needle = str(keyword).casefold()
        if needle.isalnum() and len(needle) <= 3:
            if re.search(rf"\b{re.escape(needle)}\b", haystack):
                return True
        elif needle in haystack:
            return True
    return False


def _best_external_url(urls):
    return max(
        urls,
        key=lambda value: (
            urlparse(value).path not in {"", "/"},
            len(urlparse(value).path),
            len(urlparse(value).query),
        ),
    )


def main():
    config = load_config()
    items = collect(config)
    write_items(items)
    print(f"Collected {len(items)} Community Pulse posts")


if __name__ == "__main__":
    main()
