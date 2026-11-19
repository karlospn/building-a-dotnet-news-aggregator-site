import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml
from dateutil import parser as dateparser

from common import sanitize_html


CONFIG_PATH = Path("config/ai_release_sources.yml")
OUTPUT_PATH = Path("site/dotnetramblings/data/ai_releases.json")
GITHUB_API = "https://api.github.com"


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not config.get("sources"):
        raise ValueError("AI release configuration must contain sources")
    return config


def fetch_releases(repository, token=None):
    request = Request(
        f"{GITHUB_API}/repos/{repository}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DotNetRamblings/1.0",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def build_release_data(
    config, fetcher=fetch_releases, now=None, token=None, previous_records=()
):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(config.get("retention_days", 365)))
    max_per_source = int(config.get("max_releases_per_source", 24))
    records = []
    missing_sources = 0
    for source in config["sources"]:
        pattern = re.compile(source["tag_regex"])
        repository = source["repository"]
        try:
            fetched = fetcher(repository, token)
        except HTTPError as error:
            if error.code != 404:
                raise
            missing_sources += 1
            cached = sorted(
                (
                    record
                    for record in previous_records
                    if record["repository"] == repository
                    and pattern.search(record["tagName"])
                    and datetime.fromisoformat(record["publishedAt"]) >= cutoff
                ),
                key=lambda record: record["publishedAt"],
                reverse=True,
            )[:max_per_source]
            records.extend(cached)
            logging.warning(
                "GitHub returned 404 for %s. Retaining %d cached releases.",
                repository, len(cached),
            )
            continue
        releases = [
            release
            for release in fetched
            if not release.get("draft")
            and not release.get("prerelease")
            and pattern.search(release.get("tag_name", ""))
            and _published_at(release) >= cutoff
        ]
        releases.sort(key=_published_at, reverse=True)
        releases = releases[:max_per_source]
        versions = [_version_tuple(release.get("tag_name", "")) for release in releases]
        for index, release in enumerate(releases):
            previous_version = versions[index + 1] if index + 1 < len(versions) else None
            records.append(
                normalize_release(
                    source,
                    release,
                    previous_version=previous_version,
                )
            )
    if missing_sources and missing_sources == len(config["sources"]):
        raise RuntimeError("GitHub returned 404 for every configured release source")
    records.sort(key=lambda item: item["publishedAt"], reverse=True)
    return records


def normalize_release(source, release, previous_version=None):
    tag = release.get("tag_name", "")
    version = _version_text(tag)
    body = release.get("body") or ""
    change_type = classify_release(tag, body, previous_version)
    return {
        "id": f"{source['repository']}:{release['id']}",
        "product": source["product"],
        "version": version,
        "tagName": tag,
        "changeType": change_type,
        "publishedAt": _published_at(release).isoformat(),
        "title": f"{source['product']} {version}",
        "summary": summarize_release(body),
        "breaking": change_type in {"breaking-change", "major-release", "deprecation"},
        "technologies": source.get("technologies", []),
        "sourceUrl": release["html_url"],
        "repository": source["repository"],
        "official": bool(source.get("official", False)),
    }


def classify_release(tag, body, previous_version=None):
    summary = summarize_release(body, limit=600)
    text = f"{tag} {summary}".casefold()
    version = _version_tuple(tag)
    if re.search(r"\b(cve-\d+|security (?:release|fix|update)|critical vulnerabilit)", text):
        return "security"
    if re.search(
        r"\b(deprecation|deprecates|end of support|will be removed|removes? support)\b"
        r"|\bremov(?:e|es|ed|ing) (?:the )?deprecated\b",
        text,
    ):
        return "deprecation"
    if "breaking change" in text or "breaking-change" in text:
        return "breaking-change"
    if version and previous_version and version[0] > previous_version[0]:
        return "major-release"
    return "sdk-release"


def summarize_release(body, limit=280):
    lines = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith("#")
            or line.startswith("<!--")
            or re.match(r"^[-*]\s+\[[ xX]\]", line)
            or line.casefold().startswith("full changelog:")
            or line.casefold().startswith("see full changelog:")
            or re.fullmatch(r"[a-f0-9]{7,40}", line.casefold())
        ):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"[`*_~]", "", line)
        text = sanitize_html(line)
        if text:
            lines.append(text)
        if len(" ".join(lines)) >= limit:
            break
    summary = " ".join(lines) or "See the official release notes for details."
    if len(summary) <= limit:
        return summary
    return f"{summary[: limit + 1].rsplit(' ', 1)[0]}…"


def write_release_data(records, path=OUTPUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _published_at(release):
    value = release.get("published_at") or release.get("created_at")
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    parsed = dateparser.parse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _version_tuple(tag):
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)", tag)
    return tuple(int(part) for part in match.groups()) if match else None


def _version_text(tag):
    version = _version_tuple(tag)
    return ".".join(str(part) for part in version) if version else tag


def main():
    config = load_config()
    previous_records = []
    if OUTPUT_PATH.exists():
        previous_records = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    records = build_release_data(
        config,
        token=os.getenv("GITHUB_TOKEN"),
        previous_records=previous_records,
    )
    write_release_data(records)
    print(f"Collected {len(records)} .NET AI releases")


if __name__ == "__main__":
    main()
