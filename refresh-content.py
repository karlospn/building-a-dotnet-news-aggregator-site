"""Reapply quality rules to existing pages and archive metadata, without fetching or pruning."""

import json
from pathlib import Path

import yaml

from common import enrich_item, parse_yml_files
from archive import ARCHIVE_PATH, CONTENT_ROOTS, read_content_item


def refresh_record(record, sources):
    source = sources.get(record["sourceId"], {})
    inferred = record.get("languageInferred", False)
    item = enrich_item({
        "title": record["title"], "url": record["link"], "date": record["date"],
        "summary": record.get("summary", ""), "content_type": record["contentType"],
        "image": record.get("thumbnail", ""), "duration": record.get("duration", ""),
        "reading_minutes": record.get("readingMinutes"),
        "language": "" if inferred else record.get("language", ""),
    })
    result = dict(record)
    result.update({
        "summary": item["summary"], "topics": item["topics"],
        "aiSubtopics": item["ai_subtopics"], "readingMinutes": item["reading_minutes"],
        "fallbackThumbnail": item["fallback_thumbnail"], "whyItMatters": item["why_it_matters"],
        "sourceUrl": source.get("website", record.get("sourceUrl", "")),
        **{key: item[key] for key in ("language", "languageInferred", "durationSeconds", "videoFormat", "aiRelevance")},
    })
    if not str(record.get("thumbnail", "")).startswith("http"):
        result["thumbnail"] = item["fallback_thumbnail"]
    return result


def main():
    sources = {s["id"]: s for s in parse_yml_files(Path("data").glob("*.yml"))}
    records = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    records = {r["link"]: refresh_record(r, sources) for r in records}
    count = 0
    for root in CONTENT_ROOTS:
        for path in root.rglob("*.md"):
            _, front, _ = path.read_text(encoding="utf-8").split("---", 2)
            metadata = yaml.safe_load(front)
            record = refresh_record(read_content_item(path), sources)
            for key in ("topics", "aiSubtopics", "readingMinutes", "fallbackThumbnail", "thumbnail", "sourceUrl", "whyItMatters", "language", "languageInferred", "durationSeconds", "videoFormat", "aiRelevance"):
                if record.get(key) is not None:
                    metadata[key] = record[key]
            metadata["tags"] = list(record["topics"])
            path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False, width=1000) + "---\n" + record["summary"] + "\n\n- " + record["whyItMatters"] + "\n- Link to " + record["contentType"] + ": " + record["link"] + "\n", encoding="utf-8")
            records[record["link"]] = record
            count += 1
    ARCHIVE_PATH.write_text(json.dumps(sorted(records.values(), key=lambda r: r["date"], reverse=True), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Refreshed {count} pages and {len(records)} archive records; no content removed")


if __name__ == "__main__":
    main()
