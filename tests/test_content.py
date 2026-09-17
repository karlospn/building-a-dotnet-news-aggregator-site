import glob
import unittest
from pathlib import Path

import yaml

from common import canonicalize_url, parse_yml_files


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
                ):
                    self.assertIn(field, metadata)
                self.assertIn(metadata["sourceId"], self.source_ids)
                self.assertIn(metadata["contentType"], {"article", "video"})
                self.assertTrue(metadata["topics"])
                canonical_url = canonicalize_url(metadata["canonicalUrl"])
                self.assertNotIn(canonical_url, urls)
                urls.add(canonical_url)

                if metadata["contentType"] == "video":
                    self.assertRegex(
                        metadata["thumbnail"],
                        r"^https://i\.ytimg\.com/vi/[^/]+/hqdefault\.jpg$",
                    )


if __name__ == "__main__":
    unittest.main()
