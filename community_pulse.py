import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import feedparser
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from common import canonicalize_url, classify_topics, sanitize_html


CONFIG_PATH = Path("config/community_pulse_sources.yml")
OUTPUT_PATH = Path("site/dotnetramblings/data/community_pulse.json")
DISCUSSIONS_PATH = Path("site/dotnetramblings/data/community_discussions.json")
SOURCES_PATH = Path("site/dotnetramblings/data/community_sources.json")
HEALTH_PATH = Path("site/dotnetramblings/data/community_source_health.json")
ARCHIVE_PATH = Path("site/dotnetramblings/static/archive.json")
BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
SOCIAL_HOSTS = {
    "bsky.app",
    "public.api.bsky.app",
    "dotnet.social",
    "hachyderm.io",
    "mastodon.social",
    "fosstodon.org",
    "reddit.com",
    "www.reddit.com",
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
    if parsed.get("status", 200) >= 400:
        raise ValueError(f"HTTP {parsed.status}")
    if parsed.bozo and not parsed.entries:
        raise ValueError(str(parsed.bozo_exception))
    if not parsed.entries and not parsed.feed.get("title"):
        raise ValueError("Mastodon feed returned no RSS entries or channel metadata")
    return parsed


def fetch_reddit(feed_url):
    parsed = feedparser.parse(
        feed_url,
        request_headers={"User-Agent": "DotNetRamblings/1.0 (community links; GitHub: karlospn)"},
    )
    if parsed.get("status", 200) >= 400:
        raise ValueError(f"HTTP {parsed.status}")
    if parsed.bozo and not parsed.entries:
        raise ValueError(str(parsed.bozo_exception))
    if not parsed.entries:
        raise ValueError("Reddit feed returned no entries")
    return parsed


def parse_reddit(parsed):
    items = []
    for entry in parsed.entries:
        post_url = entry.get("link", "")
        post = urlparse(post_url)
        if (post.scheme != "https" or post.hostname not in {"reddit.com", "www.reddit.com"}
                or not post.path.startswith("/r/dotnet/comments/")):
            continue
        content = entry.get("summary", "")
        soup = BeautifulSoup(content, "html.parser")
        markers = {"[removed]", "[deleted]"}
        if (entry.get("author") in markers or entry.get("title") in markers
                or not markers.isdisjoint(soup.stripped_strings)):
            continue
        urls = _external_urls(
            [anchor.get("href", "") for anchor in soup.find_all("a")],
            excluded_host=urlparse(post_url).netloc.lower(),
        )
        urls = [url for url in urls if not _is_reddit_link(url)]
        if not urls:
            continue
        author = entry.get("author", "Reddit member")
        items.append(
            _item(
                {"id": f"reddit:{author}", "name": author, "default_topics": [".NET"]},
                platform="reddit",
                handle=author,
                published=entry.get("published"),
                text=sanitize_html(entry.get("title", "")),
                post_url=post_url,
                external_url=_best_external_url(urls),
            )
        )
    return [item for item in items if item]


def _is_reddit_link(url):
    host = urlparse(url).hostname or ""
    return any(
        host == domain or host.endswith("." + domain)
        for domain in ("reddit.com", "redd.it", "redditmedia.com", "redditstatic.com")
    )


def fetch_hacker_news(terms, cutoff):
    hits = {}
    for term in terms:
        page = 0
        while True:
            query = urlencode({
                "query": term, "tags": "story", "restrictSearchableAttributes": "title",
                "numericFilters": f"created_at_i>={int(cutoff.timestamp())},num_comments>0",
                "hitsPerPage": 100, "page": page,
            })
            request = Request(f"{HN_SEARCH}?{query}", headers={"User-Agent": "DotNetRamblings/1.0"})
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            hits.update((hit["objectID"], hit) for hit in payload["hits"])
            page += 1
            if page >= payload["nbPages"]:
                break
    return hits.values()


def parse_hacker_news(hits, terms):
    title_pattern = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, terms)) + r")(?!\w)", re.I)
    items = []
    for hit in hits:
        title = hit.get("title") or ""
        if not title_pattern.search(title) or (hit.get("num_comments") or 0) < 1:
            continue
        urls = _external_urls([hit.get("url")], excluded_host="news.ycombinator.com")
        if not urls or _is_reddit_link(urls[0]):
            continue
        author = hit.get("author") or "Hacker News member"
        item = _item(
            {"id": f"hacker-news:{author}", "name": author, "default_topics": [".NET"]},
            platform="hacker-news", handle=author, published=hit.get("created_at"),
            text=title, post_url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
            external_url=urls[0],
        )
        if item:
            items.append(item)
    return items


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


def collect(
    config, now=None, bluesky_fetcher=fetch_bluesky,
    mastodon_fetcher=fetch_mastodon, health=None,
):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(config.get("retention_days", 7)))
    candidates = []
    successful_accounts = 0
    attempted_accounts = 0

    for identity in config["identities"]:
        for account in identity.get("accounts", []):
            attempted_accounts += 1
            source = {
                "identityId": identity["id"],
                "platform": account["platform"],
                "status": "ok",
                "candidates": 0,
                "published": 0,
            }
            if health is not None:
                health.append(source)
            try:
                if account["platform"] == "bluesky":
                    payload = bluesky_fetcher(account["handle"])
                    posts = parse_bluesky(payload, identity, account)
                elif account["platform"] == "mastodon":
                    parsed = mastodon_fetcher(account["feed"])
                    posts = parse_mastodon(parsed, identity, account)
                else:
                    raise ValueError(f"Unsupported social platform: {account['platform']}")
                source["candidates"] = len(posts)
                candidates.extend(posts)
                successful_accounts += 1
            except Exception as error:
                source["status"] = "error"
                source["error"] = str(error)
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
    result = deduplicate_and_cap(
        retained,
        int(config.get("max_posts_per_identity_per_day", 2)),
    )
    if health is not None:
        for source in health:
            source["published"] = sum(
                item["identityId"] == source["identityId"]
                and (
                    item["platform"] == source["platform"]
                    or any(
                        reference["platform"] == source["platform"]
                        for reference in item.get("alsoOn", [])
                    )
                )
                for item in result
            )
        for platform in ("bluesky", "mastodon"):
            platform_sources = [source for source in health if source["platform"] == platform]
            print(
                f"{platform}: {sum(source['published'] for source in platform_sources)} "
                f"posts from {sum(source['status'] == 'ok' for source in platform_sources)}"
                f"/{len(platform_sources)} reachable accounts"
            )
    return result


def _discussion_link_key(url):
    parsed = urlparse(canonicalize_url(url))
    host = parsed.netloc
    path = parsed.path
    # A GitHub Pages project homepage and its repository can host the same announcement.
    if host.endswith(".github.io") and re.fullmatch(r"/[\w.-]+(?:/index\.html)?", path):
        owner = host.removesuffix(".github.io")
        path = f"/{owner}{path.removesuffix('/index.html')}"
        host = "github.com"
    if host == "github.com" and re.fullmatch(r"/[\w.-]+/[\w.-]+", path):
        path = path.lower()
    return host, path, parsed.query


def _refresh_reddit(feed_url, cached):
    feed = fetch_reddit(feed_url)
    fetched_posts = {entry.get("link") for entry in feed.entries}
    return parse_reddit(feed) + [item for item in cached if item["postUrl"] not in fetched_posts]


def _select_reddit(candidates):
    retained = [
        item for item in candidates
        if _is_relevant(item, [".net", "dotnet", "c#", "asp.net", "blazor",
                                "azure", "nuget", "roslyn", "ef core", "aspire"])
    ]
    unique = deduplicate_and_cap(retained, max_per_day=100000)
    daily_counts = defaultdict(int)
    result = []
    for item in unique:
        day = _published_at(item).date().isoformat()
        if daily_counts[day] >= 4:
            continue
        daily_counts[day] += 1
        result.append(item)
    return result


def collect_discussions(
    pulse_items, now=None, *, feed_url=None, hacker_news_terms=(), health=None,
    existing_path=DISCUSSIONS_PATH,
):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=7)
    cached = defaultdict(list)
    for item in _existing_items(cutoff, existing_path):
        secondary_threads = item.pop("alsoOn", [])
        for record in [item, *secondary_threads]:
            cached[record["platform"]].append(record)

    sources = [("reddit", "reddit-dotnet", feed_url)]
    if hacker_news_terms:
        sources.append(("hacker-news", "hacker-news", hacker_news_terms))
    excluded_links = {_discussion_link_key(url) for url in _archive_links()}
    excluded_links.update(_discussion_link_key(item["externalUrl"]) for item in pulse_items)
    excluded_text = {_text_key(item["excerpt"]) for item in pulse_items}
    candidates = []
    statuses = []
    for platform, source_id, setting in sources:
        records = cached[platform]
        source = {"identityId": source_id, "platform": platform, "status": "disabled"}
        if setting:
            try:
                if platform == "reddit":
                    records = _refresh_reddit(feed_url, records)
                else:
                    hits = fetch_hacker_news(hacker_news_terms, cutoff)
                    records = parse_hacker_news(hits, hacker_news_terms)
                source["status"] = "ok"
            except Exception as error:
                source.update(status="error", error=str(error))
                print(f"Failed to refresh {platform} discussions: {error}")
        retained = [
            item for item in records
            if _published_at(item) >= cutoff
            and _discussion_link_key(item["externalUrl"]) not in excluded_links
            and _text_key(item["excerpt"]) not in excluded_text
        ]
        candidates.extend(_select_reddit(retained) if platform == "reddit" else retained)
        statuses.append(source)

    attempted_statuses = {s["status"] for s in statuses} - {"disabled"}
    if attempted_statuses == {"error"} and not existing_path.exists():
        raise RuntimeError("All configured discussion sources failed before the first collection")
    stories = {}
    represented = set()
    counts = defaultdict(int)
    for item in sorted(candidates, key=_published_at, reverse=True):
        key = _discussion_link_key(item["externalUrl"])
        platform = item["platform"]
        if (key, platform) in represented:
            continue
        represented.add((key, platform))
        if key in stories:
            # Keep each thread's date and author so a cached copy can expire independently.
            stories[key].setdefault("alsoOn", []).append(item)
        else:
            stories[key] = item
        counts[platform] += 1
    for source in statuses:
        source["published"] = counts[source["platform"]]
        print(f"{source['platform']} ({source['status']}): {source['published']} linked discussions")
    if health is not None:
        health.extend(statuses)
    return list(stories.values())


def deduplicate_and_cap(items, max_per_day=2):
    ordered = sorted(items, key=_published_at, reverse=True)
    seen_ids = set()
    seen_urls = set()
    seen_text = set()
    by_url = {}
    by_text = {}
    daily_counts = defaultdict(int)
    result = []
    for item in ordered:
        external_url = canonicalize_url(item["externalUrl"])
        text_key = _text_key(item["excerpt"])
        day_key = (item["identityId"], _published_at(item).date().isoformat())
        duplicate = by_url.get(external_url) or (by_text.get(text_key) if text_key else None)
        if duplicate and duplicate["identityId"] == item["identityId"] and duplicate["platform"] != item["platform"]:
            also_on = duplicate.setdefault("alsoOn", [])
            reference = {"platform": item["platform"], "postUrl": item["postUrl"]}
            if reference not in also_on:
                also_on.append(reference)
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
            by_text[text_key] = item
        by_url[external_url] = item
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


def _existing_items(cutoff, path=OUTPUT_PATH):
    if not path.exists():
        return []
    return [
        item
        for item in json.loads(path.read_text(encoding="utf-8"))
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
    health = []
    items = collect(config, health=health)
    write_items(items)
    sources = [
        {
            "id": identity["id"],
            "name": identity["name"],
            "accounts": [
                {
                    "platform": account["platform"],
                    "url": (
                        f"https://bsky.app/profile/{account['handle']}"
                        if account["platform"] == "bluesky"
                        else account["feed"].removesuffix(".rss")
                    ),
                }
                for account in identity.get("accounts", [])
            ],
        }
        for identity in config["identities"]
    ]
    write_items(sources, SOURCES_PATH)
    discussions = collect_discussions(
        items, feed_url=config.get("reddit_feed_url"),
        hacker_news_terms=config.get("hacker_news_terms", []), health=health,
    )
    write_items(health, HEALTH_PATH)
    write_items(discussions, DISCUSSIONS_PATH)
    print(f"Collected {len(items)} Community Pulse posts")


if __name__ == "__main__":
    main()
