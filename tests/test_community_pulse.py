import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from feedparser import FeedParserDict

from community_pulse import (
    collect,
    collect_discussions,
    deduplicate_and_cap,
    fetch_mastodon,
    fetch_reddit,
    parse_bluesky,
    parse_mastodon,
    parse_reddit,
)


IDENTITY = {
    "id": "developer",
    "name": "Developer",
    "default_topics": [".NET"],
}


class CommunityPulseTests(unittest.TestCase):
    @patch("community_pulse.feedparser.parse", return_value=FeedParserDict({
        "bozo": False, "entries": [], "status": 502, "feed": {},
    }))
    def test_http_failure_is_not_reported_as_reachable(self, _parse):
        with self.assertRaisesRegex(ValueError, "HTTP 502"):
            fetch_mastodon("https://social.example/@developer.rss")
        with self.assertRaisesRegex(ValueError, "HTTP 502"):
            fetch_reddit()

    def test_bluesky_ignores_reposts_and_prefers_real_article_link(self):
        payload = {
            "feed": [
                {
                    "post": {
                        "uri": "at://did:plc:one/app.bsky.feed.post/abc",
                        "indexedAt": "2026-09-21T10:00:00Z",
                        "record": {
                            "text": "ASP.NET article dev.to/example/article",
                            "createdAt": "2026-09-21T10:00:00Z",
                            "facets": [
                                {
                                    "features": [
                                        {
                                            "$type": "app.bsky.richtext.facet#link",
                                            "uri": "https://asp.net/",
                                        }
                                    ]
                                },
                                {
                                    "features": [
                                        {
                                            "$type": "app.bsky.richtext.facet#link",
                                            "uri": "https://dev.to/example/article",
                                        }
                                    ]
                                },
                            ],
                        },
                    }
                },
                {
                    "reason": {"$type": "app.bsky.feed.defs#reasonRepost"},
                    "post": {},
                },
            ]
        }
        items = parse_bluesky(payload, IDENTITY, {"handle": "developer.test"})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["externalUrl"], "https://dev.to/example/article")

    def test_mastodon_ignores_replies(self):
        parsed = FeedParserDict(
            {
                "feed": {"title": "Developer"},
                "entries": [
                    {
                        "link": "https://social.example/@dev/1",
                        "published": "2026-09-21T10:00:00Z",
                        "summary": (
                            'RE: a personal reply '
                            '<a href="https://example.com/article">link</a>'
                        ),
                    },
                    {
                        "link": "https://social.example/@dev/2",
                        "published": "2026-09-21T11:00:00Z",
                        "summary": (
                            '.NET performance article '
                            '<a class="u-url mention" href="https://other.social/@person">'
                            '@person</a> '
                            '<a href="https://example.com/dotnet">link</a>'
                        ),
                    },
                ],
            }
        )
        items = parse_mastodon(parsed, IDENTITY, {"feed": "https://social.example/feed"})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["externalUrl"], "https://example.com/dotnet")

    def test_cross_platform_dedup_and_daily_cap(self):
        items = [
            self.item("new", "bluesky", "2026-09-21T12:00:00Z", "https://a.dev/1", "Same .NET post a.dev/1"),
            self.item("duplicate", "mastodon", "2026-09-21T11:00:00Z", "https://b.dev/2", "Same .NET post https://b.dev/2"),
            self.item("second", "bluesky", "2026-09-21T10:00:00Z", "https://c.dev/3", "Another C# post"),
            self.item("capped", "mastodon", "2026-09-21T09:00:00Z", "https://d.dev/4", "Third ASP.NET post"),
        ]
        result = deduplicate_and_cap(items, max_per_day=2)
        self.assertEqual([item["id"] for item in result], ["new", "second"])
        self.assertEqual(result[0]["alsoOn"], [{
            "platform": "mastodon",
            "postUrl": "https://social.example/duplicate",
        }])

    def test_reddit_only_accepts_external_links(self):
        parsed = FeedParserDict({
            "entries": [
                {
                    "link": "https://www.reddit.com/r/dotnet/comments/abc/post/",
                    "published": "2026-09-22T10:00:00Z",
                    "author": "/u/developer",
                    "title": "A .NET performance article",
                    "summary": (
                        '<a href="https://www.reddit.com/r/dotnet/">Community</a>'
                        '<a href="https://example.com/dotnet">Read the article</a>'
                    ),
                },
                {
                    "link": "https://www.reddit.com/r/dotnet/comments/def/question/",
                    "published": "2026-09-22T11:00:00Z",
                    "title": "Question about .NET",
                    "summary": '<a href="https://www.reddit.com/r/dotnet/">Community</a>',
                },
            ],
        })
        items = parse_reddit(parsed)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["externalUrl"], "https://example.com/dotnet")
        self.assertEqual(items[0]["platform"], "reddit")

    @patch("community_pulse._archive_links", return_value={"https://example.com/archived"})
    def test_discussions_exclude_pulse_and_archive_links(self, _archive):
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        entries = []
        for key in ("shared", "archived", "fresh", "old"):
            entries.append({
                "link": f"https://www.reddit.com/r/dotnet/comments/{key}/post/",
                "published": "2026-09-10T10:00:00Z" if key == "old" else "2026-09-23T10:00:00Z",
                "title": f".NET {key} discussion",
                "summary": f'<a href="https://example.com/{key}">Link</a>',
            })
        with TemporaryDirectory() as directory:
            result = collect_discussions(
                [self.item("shared", "bluesky", "2026-09-23T09:00:00Z",
                           "https://example.com/shared", ".NET shared discussion")],
                now=now,
                reddit_fetcher=lambda: FeedParserDict({"entries": entries}),
                existing_path=Path(directory) / "discussions.json",
            )
        self.assertEqual([item["externalUrl"] for item in result], ["https://example.com/fresh"])

    @patch("community_pulse._archive_links", return_value=set())
    @patch("community_pulse._existing_items", return_value=[])
    def test_collection_reports_platform_without_unique_posts(self, _existing, _archive):
        config = {
            "include_keywords": [".net"],
            "identities": [{
                **IDENTITY,
                "accounts": [{"platform": "mastodon", "feed": "https://social.example/feed"}],
            }],
        }
        parsed = FeedParserDict({
            "feed": {"title": "Developer"},
            "entries": [{
                "link": "https://social.example/@dev/1",
                "published": "2026-09-23T10:00:00Z",
                "summary": '.NET article <a href="https://example.com/story">link</a>',
            }],
        })
        health = []
        items = collect(
            config, now=datetime(2026, 9, 24, tzinfo=timezone.utc),
            mastodon_fetcher=lambda _: parsed, health=health,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(health[0]["candidates"], 1)
        self.assertEqual(health[0]["published"], 1)

    @patch("community_pulse._archive_links", return_value=set())
    @patch("community_pulse._existing_items", return_value=[])
    def test_collection_applies_seven_day_retention_and_relevance(
        self,
        _existing,
        _archive,
    ):
        config = {
            "retention_days": 7,
            "max_posts_per_identity_per_day": 2,
            "include_keywords": [".net"],
            "identities": [
                {
                    **IDENTITY,
                    "accounts": [{"platform": "bluesky", "handle": "developer.test"}],
                }
            ],
        }
        payload = {
            "feed": [
                self.bluesky_post(
                    "new",
                    "2026-09-21T10:00:00Z",
                    ".NET performance article",
                ),
                self.bluesky_post(
                    "old",
                    "2026-09-01T10:00:00Z",
                    ".NET archive article",
                ),
                self.bluesky_post(
                    "personal",
                    "2026-09-21T09:00:00Z",
                    "A personal holiday photo",
                ),
            ]
        }
        items = collect(
            config,
            now=datetime(2026, 9, 22, tzinfo=timezone.utc),
            bluesky_fetcher=lambda _handle: payload,
        )
        self.assertEqual([item["id"] for item in items], [
            self.expected_id("https://bsky.app/profile/developer.test/post/new")
        ])

    @staticmethod
    def item(identifier, platform, published, url, excerpt):
        return {
            "id": identifier,
            "identityId": "developer",
            "author": "Developer",
            "platform": platform,
            "publishedAt": published,
            "excerpt": excerpt,
            "postUrl": f"https://social.example/{identifier}",
            "externalUrl": url,
            "topics": [".NET"],
        }

    @staticmethod
    def bluesky_post(identifier, created_at, text):
        return {
            "post": {
                "uri": f"at://did:plc:one/app.bsky.feed.post/{identifier}",
                "indexedAt": created_at,
                "record": {
                    "text": text,
                    "createdAt": created_at,
                    "facets": [
                        {
                            "features": [
                                {
                                    "$type": "app.bsky.richtext.facet#link",
                                    "uri": f"https://example.com/{identifier}",
                                }
                            ]
                        }
                    ],
                },
            }
        }

    @staticmethod
    def expected_id(post_url):
        import hashlib

        return hashlib.sha1(post_url.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    unittest.main()
