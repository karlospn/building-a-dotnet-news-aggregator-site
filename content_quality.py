"""Conservative, offline metadata enrichment. Publisher metadata never assigns story topics."""

import re
from functools import lru_cache
from pathlib import Path

import yaml
from bs4 import BeautifulSoup


@lru_cache(maxsize=1)
def editorial_overrides():
    path = Path("config/content_overrides.yml")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def publisher_reading_minutes(value):
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    match = re.search(r"\b(\d{1,3})\s*(?:min(?:ute)?s?)\s+read\b", text[:180], re.I)
    return int(match[1]) if match and int(match[1]) > 0 else None


def clean_excerpt(value):
    soup = BeautifulSoup(value or "", "html.parser")
    for element in soup.select("script, style, nav, footer"):
        element.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    text = re.sub(r"\s*(?:The post .+? appeared first on|Continue reading\b).*?$", "", text, flags=re.I)
    text = re.sub(r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\s*", "", text, flags=re.I)
    text = re.sub(r"^\d{1,3}\s*(?:min(?:ute)?s?)\s+read\s*", "", text, flags=re.I)
    # Remove a leading promotion while retaining the description that follows its URL.
    text = re.sub(r"^(?:visit|subscribe|sign up|check out|download|get the course)\b[^\n]*?https?://\S+\s*", "", text, flags=re.I)
    return text.strip(" \u2192")


def select_excerpt(summary, content=""):
    """Extract source wording; never invent a takeaway from a truncated feed."""
    cleaned = clean_excerpt(summary)
    personal_intro = re.match(r"(?:I (?:haven.t|have not|personally)|It.s been (?:a while|awhile)|Quick update from|Happy (?:Monday|Friday))\b", cleaned, re.I)
    if not cleaned or personal_intro:
        soup = BeautifulSoup(content or "", "html.parser")
        paragraphs = [clean_excerpt(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
        for paragraph in paragraphs:
            if len(paragraph) >= 60 and re.search(r"\b(?:learn|implement|build|release|support|performance|application|database|API|SDK|code|debug|deploy)\b|\.NET|C#", paragraph, re.I):
                return paragraph
    return cleaned


def duration_seconds(value):
    if not re.fullmatch(r"\d+:\d{2}(?::\d{2})?", str(value or "")):
        return None
    parts = [int(part) for part in value.split(":")]
    if any(part >= 60 for part in parts[1:]):
        return None
    total = 0
    for part in parts:
        total = total * 60 + part
    return total or None


LANGUAGE_WORDS = {
    "en": "the this with from your how what learn using build for and you that is are",
    "es": "el los las una cómo qué para con del por más este esta aprender usando",
    "pt": "os uma como você para com dos das mais não neste nesta usando seu sua",
    "fr": "les une avec dans pour des vous votre comment cette est apprendre",
    "de": "der die das und mit für von wie ist eine einer nicht lernen",
    "cs": "jsem jak pro na se si že ale tak tento byla bylo jsem tím",
}


def detect_language(text, declared=""):
    code = str(declared or "").lower().replace("_", "-").split("-")[0]
    if re.fullmatch(r"[a-z]{2,3}", code) and code != "und":
        return code, False
    words = set(re.findall(r"[^\W\d_]+", text.casefold()))
    scores = sorted(((len(words & set(v.split())), k) for k, v in LANGUAGE_WORDS.items()), reverse=True)
    if scores[0][0] >= 3 and scores[0][0] >= scores[1][0] + 2:
        return scores[0][1], True
    return "und", False


def video_format(title, summary, duration):
    text = f"{title} {summary}".casefold()
    if duration is not None and duration < 120:
        return "clip"
    if re.search(r"\b(?:podcast|mixture of experts|interview)\b", text):
        return "podcast"
    if re.search(r"(?<!\w)(?:keynote|conference talk|ndc|dotnetconf|\.net conf)(?!\w)", text):
        return "talk"
    if re.search(r"\b(?:tutorial|walkthrough|workshop|hands.on|step.by.step|how to)\b", text):
        return "tutorial"
    return "other"


def discovery_metadata(title, summary, topics, content_type, duration="", language="", override=None):
    override = override or {}
    code, inferred = detect_language(f"{title} {summary}", override.get("language", language))
    seconds = duration_seconds(duration) if content_type == "video" else None
    return {
        "language": code,
        "languageInferred": inferred,
        "durationSeconds": seconds,
        "videoFormat": (override.get("videoFormat") or video_format(title, summary, seconds)) if content_type == "video" else "",
        "aiRelevance": "dotnet" if ".NET" in topics else "general",
    }
