import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import yaml
from feedparser import FeedParserDict

from common import (
    _valid_image_url,
    canonicalize_url,
    clean_content,
    convert_rss_data_to_md,
    deduplicate_video_items,
    enrich_item,
    normalize_title,
    normalize_title_key,
    parse_yml_files,
)
from news import fetch_rss_feeds, get_rss_data
from youtube import _format_duration, fetch_youtube_channels, get_channel_id


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
        self.assertEqual(item["fallback_thumbnail"], "images/dotnet.png")

    def test_title_normalization_decodes_entities_and_markup(self):
        self.assertEqual(
            normalize_title(
                "The &amp;quot;Free Lunch&amp;quot; &lt;b&gt;That Cost Millions&lt;/b&gt;"
            ),
            'The "Free Lunch" That Cost Millions',
        )
        self.assertEqual(
            normalize_title_key("What&#39;s New: .NET 10?"),
            normalize_title_key("What's New — .NET 10!"),
        )

    def test_video_title_deduplication_keeps_newest_within_window(self):
        items = [
            {
                "title": "Building AI Apps &amp; Faster",
                "date": "2026-09-18T10:00:00Z",
                "url": "https://youtube.com/watch?v=new",
            },
            {
                "title": "Building AI Apps & Faster",
                "date": "2026-09-17T10:00:00Z",
                "url": "https://youtube.com/watch?v=old",
            },
            {
                "title": "Building AI Apps & Faster",
                "date": "2026-08-01T10:00:00Z",
                "url": "https://youtube.com/watch?v=episode",
            },
        ]
        deduplicated = deduplicate_video_items(items)
        self.assertEqual(
            [item["url"] for item in deduplicated],
            [
                "https://youtube.com/watch?v=new",
                "https://youtube.com/watch?v=episode",
            ],
        )

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

    def test_image_url_validation_rejects_tracking_pixels(self):
        self.assertEqual(
            _valid_image_url(
                "/images/article.jpg",
                "https://example.com/posts/one",
                width="640",
                height="360",
            ),
            "https://example.com/images/article.jpg",
        )
        self.assertEqual(
            _valid_image_url(
                "https://example.com/tracking/pixel.gif",
                width="1",
                height="1",
            ),
            "",
        )
        self.assertEqual(_valid_image_url("data:image/png;base64,abc"), "")

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

    @patch("youtube.time.sleep")
    @patch("youtube.record_feed_health")
    @patch("youtube.existing_title_dates", return_value={})
    @patch("youtube.existing_urls", return_value=set())
    @patch("youtube.get_youtube_client")
    @patch("youtube.get_youtube_data")
    def test_cross_channel_video_duplicates_keep_newest(
        self,
        get_data,
        _client,
        _urls,
        _titles,
        _health,
        _sleep,
    ):
        get_data.side_effect = [
            [
                {
                    "title": "What&#39;s New in .NET",
                    "date": "2026-09-17T10:00:00Z",
                    "canonical_url": "https://youtube.com/watch?v=old",
                    "source_id": "one",
                    "source_title": "One",
                    "rank": 50,
                }
            ],
            [
                {
                    "title": "What's New in .NET",
                    "date": "2026-09-18T10:00:00Z",
                    "canonical_url": "https://youtube.com/watch?v=new",
                    "source_id": "two",
                    "source_title": "Two",
                    "rank": 50,
                }
            ],
        ]
        sources = [
            {"feed": "https://youtube.com/@one", "title": "One"},
            {"feed": "https://youtube.com/@two", "title": "Two"},
        ]
        items = fetch_youtube_channels(sources)
        self.assertEqual(
            [item["canonical_url"] for item in items],
            ["https://youtube.com/watch?v=new"],
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
                now=datetime(2026, 9, 17),
            )

            self.assertEqual(removed, 1)
            self.assertFalse(expired.exists())
            self.assertTrue(current.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
