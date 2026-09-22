import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from feedparser import FeedParserDict

from community_pulse import (
    collect,
    deduplicate_and_cap,
    parse_bluesky,
    parse_mastodon,
)


IDENTITY = {
    "id": "developer",
    "name": "Developer",
    "default_topics": [".NET"],
}


class CommunityPulseTests(unittest.TestCase):
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
