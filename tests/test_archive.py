import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml

import archive


def write_item(path, title, date, link):
    metadata = {
        "title": title,
        "date": date,
        "link": link,
        "canonicalUrl": link,
        "source": "Example",
        "sourceId": "example",
        "sourceUrl": "https://example.com",
        "contentType": "article",
        "topics": [".NET"],
        "thumbnail": "images/dotnet.png",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{yaml.safe_dump(metadata, sort_keys=False)}---\nSummary",
        encoding="utf-8",
    )


class ArchiveTests(unittest.TestCase):
    def test_archive_merges_content_and_removes_expired_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / "content"
            archive_path = root / "archive.json"
            write_item(
                content / "current.md",
                "Current",
                "2026-09-16T12:00:00+00:00",
                "https://example.com/current",
            )
            archive_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "Expired",
                            "date": "2025-01-01T12:00:00+00:00",
                            "link": "https://example.com/expired",
                        },
                        {
                            "title": "Archived",
                            "date": "2026-06-01T12:00:00+00:00",
                            "link": "https://example.com/archived",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch.object(archive, "CONTENT_ROOTS", (content,)),
                patch.object(archive, "ARCHIVE_PATH", archive_path),
            ):
                count = archive.build_archive(
                    now=datetime(2026, 9, 17, tzinfo=timezone.utc)
                )

            items = json.loads(archive_path.read_text(encoding="utf-8"))
            self.assertEqual(count, 2)
            self.assertEqual(
                {item["title"] for item in items},
                {"Current", "Archived"},
            )


if __name__ == "__main__":
    unittest.main()
