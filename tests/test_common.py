import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import yaml
from feedparser import FeedParserDict

from common import (
    canonicalize_url,
    clean_content,
    convert_rss_data_to_md,
    enrich_item,
    parse_yml_files,
)
from news import fetch_rss_feeds, get_rss_data
from youtube import _format_duration, get_channel_id


class CommonTests(unittest.TestCase):
    def test_canonicalize_url_removes_tracking_and_fragment(self):
        actual = canonicalize_url(
            "HTTPS://Example.com/post/?utm_source=test&keep=yes#heading"
        )
        self.assertEqual(actual, "https://example.com/post?keep=yes")

    def test_enrich_item_classifies_topics(self):
        item = enrich_item(
            {
                "title": "Deploy ASP.NET to Azure with GitHub Actions",
                "url": "https://example.com/post",
                "date": "2026-09-17T12:00:00+00:00",
                "summary": "A practical deployment tutorial.",
                "website": "https://example.com",
                "source_id": "example",
                "source_title": "Example",
                "source_description": "",
                "content_type": "article",
                "image": "",
            }
        )
        self.assertIn(".NET", item["topics"])
        self.assertIn("Azure", item["topics"])
        self.assertIn("DevOps", item["topics"])

    def test_markdown_has_independent_topic_and_tag_lists(self):
        item = enrich_item(
            {
                "title": "An article about .NET",
                "url": "https://example.com/post",
                "date": "2026-09-17T12:00:00+00:00",
                "summary": "A useful article.",
                "website": "https://example.com",
                "source_id": "example",
                "source_title": "Example",
                "source_description": "",
                "content_type": "article",
                "image": "",
            }
        )
        markdown = convert_rss_data_to_md(item)
        self.assertNotIn("&id", markdown)
        self.assertNotIn("*id", markdown)

    def test_youtube_duration_is_human_readable(self):
        self.assertEqual(_format_duration("PT1H2M3S"), "1:02:03")
        self.assertEqual(_format_duration("PT8M4S"), "8:04")

    def test_source_urls_without_a_scheme_are_normalized(self):
        with TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.yml"
            source_path.write_text(
                yaml.safe_dump(
                    {
                        "Feed": "www.youtube.com/@example",
                        "Title": "Example",
                        "Website": "example.com",
                    }
                ),
                encoding="utf-8",
            )
            source = parse_yml_files([source_path])[0]
        self.assertEqual(source["feed"], "https://www.youtube.com/@example")
        self.assertEqual(source["website"], "https://example.com")

    @patch("news.record_feed_health")
    @patch("news.extract_entry_image", return_value="")
    @patch("news.feedparser.parse")
    def test_rss_date_falls_back_to_updated(self, parse, _image, _health):
        parse.return_value = FeedParserDict(
            {
                "bozo": False,
                "entries": [
                    FeedParserDict(
                        {
                            "title": "A .NET update",
                            "link": "https://example.com/update",
                            "updated": "2026-09-17T11:00:00Z",
                            "summary": "Details",
                        }
                    )
                ],
            }
        )
        source = {
            "id": "example",
            "feed": "https://example.com/feed",
            "title": "Example",
            "website": "https://example.com",
            "description": "",
            "author": "",
        }
        items = get_rss_data(source, datetime(2026, 9, 17, 12, tzinfo=timezone.utc))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["date"], "2026-09-17T11:00:00+00:00")

    @patch("news.existing_urls", return_value=set())
    @patch("news.record_feed_health")
    @patch("news.get_rss_data", side_effect=RuntimeError("offline"))
    def test_all_rss_failures_fail_the_run(self, _get, _health, _existing):
        source = {
            "id": "example",
            "feed": "https://example.com/feed",
            "title": "Example",
            "website": "https://example.com",
            "description": "",
            "author": "",
        }
        with self.assertRaisesRegex(RuntimeError, "All RSS feeds failed"):
            fetch_rss_feeds([source])

    def test_youtube_handle_resolution_is_exact(self):
        youtube = MagicMock()
        youtube.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UC123"}]
        }
        self.assertEqual(
            get_channel_id("https://www.youtube.com/@dotnet", youtube), "UC123"
        )
        youtube.channels.return_value.list.assert_called_once_with(
            part="id", forHandle="dotnet"
        )

    def test_cleanup_only_removes_expired_date_directories(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            expired = root / "01_01_2026"
            current = root / "15_09_2026"
            unrelated = root / "drafts"
            for path in (expired, current, unrelated):
                path.mkdir()
                (path / "item.md").write_text("content", encoding="utf-8")

            removed = clean_content(
                root,
                retention_days=180,
                now=datetime(2026, 9, 17),
            )

            self.assertEqual(removed, 1)
            self.assertFalse(expired.exists())
            self.assertTrue(current.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
