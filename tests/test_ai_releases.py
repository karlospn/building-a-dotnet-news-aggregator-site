import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from urllib.error import HTTPError

from ai_releases import build_release_data, classify_release, summarize_release


class AIReleaseTests(unittest.TestCase):
    def test_collection_filters_tags_drafts_prereleases_and_old_releases(self):
        config = {
            "retention_days": 365,
            "max_releases_per_source": 2,
            "sources": [
                {
                    "repository": "example/sdk",
                    "product": "Example SDK",
                    "tag_regex": r"^dotnet-\d+\.\d+\.\d+$",
                    "technologies": [".NET", "SDKs"],
                    "official": True,
                }
            ],
        }
        releases = [
            self.release(4, "dotnet-2.0.0", "2026-09-10T00:00:00Z"),
            self.release(3, "dotnet-1.2.0", "2026-08-10T00:00:00Z"),
            self.release(2, "python-3.0.0", "2026-09-11T00:00:00Z"),
            self.release(
                1,
                "dotnet-1.1.0",
                "2026-09-12T00:00:00Z",
                prerelease=True,
            ),
        ]

        records = build_release_data(
            config,
            fetcher=lambda _repository, _token: releases,
            now=datetime(2026, 9, 20, tzinfo=timezone.utc),
        )

        self.assertEqual([record["version"] for record in records], ["2.0.0", "1.2.0"])
        self.assertEqual(records[0]["changeType"], "major-release")

    def test_404_retains_eligible_cached_releases_and_refreshes_other_sources(self):
        sources = [
            {"repository": repo, "product": repo, "tag_regex": r"^v"}
            for repo in ("example/missing", "example/new", "example/healthy")
        ]
        cached = [
            {"repository": repo, "tagName": tag, "publishedAt": date + "T00:00:00+00:00"}
            for repo, tag, date in [
                ("example/missing", "v1.0.0", "2025-01-01"),
                ("example/missing", "v1.1.0", "2026-08-10"),
                ("example/missing", "v1.2.0", "2026-08-15"),
                ("example/missing", "preview", "2026-09-01"),
                ("example/healthy", "v1.0.0", "2026-08-01"),
            ]
        ]
        missing = HTTPError("https://api.github.com", 404, "Not Found", {}, None)
        fetcher = Mock(side_effect=[
            missing, missing, [self.release(2, "v2.0.0", "2026-09-10T00:00:00Z")],
        ])
        with self.assertLogs(level="WARNING") as logs:
            records = build_release_data(
                {"sources": sources, "max_releases_per_source": 1},
                fetcher=fetcher,
                now=datetime(2026, 9, 20, tzinfo=timezone.utc),
                previous_records=cached,
            )

        self.assertEqual([record["tagName"] for record in records], ["v2.0.0", "v1.2.0"])
        self.assertIn("example/missing", logs.output[0])
        self.assertIn("example/new", logs.output[1])

    def test_all_sources_unavailable_or_other_http_errors_fail_the_refresh(self):
        config = {"sources": [{"repository": "example/sdk", "tag_regex": r"^v"}]}
        for status, expected in [(404, RuntimeError), (403, HTTPError), (503, HTTPError)]:
            with self.subTest(status=status), self.assertRaises(expected):
                build_release_data(
                    config,
                    fetcher=Mock(side_effect=HTTPError("url", status, "error", {}, None)),
                )

    def test_release_classification_uses_strong_signals(self):
        self.assertEqual(
            classify_release(
                "v1.2.0",
                "Replace deprecated dependency with its successor.",
            ),
            "sdk-release",
        )
        self.assertEqual(
            classify_release(
                "v1.2.0",
                "This release removes the deprecated Assistants API.",
            ),
            "deprecation",
        )
        self.assertEqual(
            classify_release("v1.2.0", "Security update for CVE-2026-1234."),
            "security",
        )
        self.assertEqual(
            classify_release(
                "v2.0.0",
                "Security update for CVE-2026-1234.",
                previous_version=(1, 9, 0),
            ),
            "security",
        )

    def test_summary_skips_changelog_boilerplate(self):
        self.assertEqual(
            summarize_release(
                "## What's Changed\n"
                "See full changelog: https://example.com\n"
                "Adds structured output support for .NET applications."
            ),
            "Adds structured output support for .NET applications.",
        )

    @staticmethod
    def release(identifier, tag, published_at, prerelease=False):
        return {
            "id": identifier,
            "tag_name": tag,
            "name": tag,
            "published_at": published_at,
            "created_at": published_at,
            "html_url": f"https://github.com/example/sdk/releases/tag/{tag}",
            "body": "Release notes.",
            "draft": False,
            "prerelease": prerelease,
        }


if __name__ == "__main__":
    unittest.main()
