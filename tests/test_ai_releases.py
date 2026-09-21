import unittest
from datetime import datetime, timezone

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
