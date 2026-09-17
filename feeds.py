import glob
import os
from pathlib import Path

import yaml

from common import classify_topics, parse_yml_files
from youtube import is_youtube_channel


def main():
    file_paths = glob.glob(os.path.join("./data", "*.yml"))
    feeds = []
    for source in parse_yml_files(file_paths):
        feeds.append(
            {
                "id": source["id"],
                "feed": source["feed"],
                "title": source["title"],
                "website": source["website"],
                "description": source["description"],
                "author": source["author"],
                "source": "YouTube channel"
                if is_youtube_channel(source["feed"])
                else "RSS feed",
                "topics": classify_topics(
                    f"{source['title']} {source['description']} {source['website']}"
                ),
            }
        )

    front_matter = {
        "title": "Sources",
        "layout": "feeds",
        "feeds": sorted(feeds, key=lambda value: value["title"].lower()),
    }
    output = "---\n" + yaml.safe_dump(
        front_matter, allow_unicode=True, sort_keys=False, width=1000
    ) + "---\n"
    Path("site/dotnetramblings/content/feeds.md").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
