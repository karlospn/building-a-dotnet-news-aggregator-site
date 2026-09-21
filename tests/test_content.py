import glob
import json
import unittest
from datetime import datetime
from pathlib import Path

import yaml

from common import canonicalize_url, normalize_title, normalize_title_key, parse_yml_files


class GeneratedContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = parse_yml_files(glob.glob("./data/*.yml"))
        cls.source_ids = {source["id"] for source in cls.sources}

    def test_sources_have_absolute_urls(self):
        for source in self.sources:
            with self.subTest(source=source["id"]):
                self.assertRegex(source["feed"], r"^https?://")
                self.assertRegex(source["website"], r"^https?://")

    def test_generated_content_has_valid_metadata_and_unique_urls(self):
        urls = set()
        files = list(Path("site/dotnetramblings/content/post").rglob("*.md"))
        files += list(Path("site/dotnetramblings/content/videos").rglob("*.md"))
        self.assertGreater(len(files), 0)

        for path in files:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                _, front_matter, _ = text.split("---", 2)
                metadata = yaml.safe_load(front_matter)
                for field in (
                    "title",
                    "date",
                    "link",
                    "canonicalUrl",
                    "source",
                    "sourceId",
                    "contentType",
                    "topics",
                    "thumbnail",
                    "fallbackThumbnail",
                ):
                    self.assertIn(field, metadata)
                self.assertIn(metadata["sourceId"], self.source_ids)
                self.assertIn(metadata["contentType"], {"article", "video"})
                self.assertEqual(metadata["title"], normalize_title(metadata["title"]))
                self.assertTrue(metadata["topics"])
                fallback = Path("site/dotnetramblings/static") / metadata["fallbackThumbnail"]
                self.assertTrue(fallback.is_file(), fallback)
                canonical_url = canonicalize_url(metadata["canonicalUrl"])
                self.assertNotIn(canonical_url, urls)
                urls.add(canonical_url)

                if metadata["contentType"] == "video":
                    self.assertRegex(
                        metadata["thumbnail"],
                        r"^https://i\.ytimg\.com/vi/[^/]+/hqdefault(?:_live)?\.jpg$",
                    )

    def test_archive_contains_every_current_content_item(self):
        archive_items = json.loads(
            Path("site/dotnetramblings/static/archive.json").read_text(encoding="utf-8")
        )
        archive_urls = {
            canonicalize_url(item["link"])
            for item in archive_items
        }
        content_urls = set()
        roots = (
            Path("site/dotnetramblings/content/post"),
            Path("site/dotnetramblings/content/videos"),
        )
        for root in roots:
            for path in root.rglob("*.md"):
                _, front_matter, _ = path.read_text(encoding="utf-8").split("---", 2)
                metadata = yaml.safe_load(front_matter)
                content_urls.add(canonicalize_url(metadata["canonicalUrl"]))
        self.assertTrue(content_urls.issubset(archive_urls))

    def test_archive_video_titles_are_unique_within_seven_days(self):
        archive_items = json.loads(
            Path("site/dotnetramblings/static/archive.json").read_text(encoding="utf-8")
        )
        videos = sorted(
            (item for item in archive_items if item["contentType"] == "video"),
            key=lambda item: item["date"],
            reverse=True,
        )
        seen = {}
        for video in videos:
            key = normalize_title_key(video["title"])
            published = datetime.fromisoformat(video["date"].replace("Z", "+00:00"))
            with self.subTest(title=video["title"]):
                for existing in seen.get(key, []):
                    self.assertGreater(
                        abs(published - existing).total_seconds(),
                        7 * 24 * 60 * 60,
                    )
            seen.setdefault(key, []).append(published)


if __name__ == "__main__":
    unittest.main()
