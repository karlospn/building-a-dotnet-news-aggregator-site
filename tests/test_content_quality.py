import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from common import enrich_item, classify_topics
from content_quality import clean_excerpt, select_excerpt, duration_seconds, detect_language, video_format
from youtube import get_youtube_data


class ContentQualityTests(unittest.TestCase):
    def test_excerpt_removes_read_time_date_and_syndication_tail(self):
        raw = "November 13, 2026 9 minutes read <p>A closed class limits its subclasses.</p> Continue reading C# Classes The post C# Classes appeared first on NDepend Blog."
        self.assertEqual(clean_excerpt(raw), "A closed class limits its subclasses.")
        item = enrich_item({"title": "C# classes", "url": "https://example.com/a", "summary": raw, "content": "word " * 3500})
        self.assertEqual(item["reading_minutes"], 9)

    def test_excerpt_removes_promotion_without_losing_description(self):
        self.assertEqual(clean_excerpt("Visit our podcast page → https://example.com/promo How does retrieval work?"), "How does retrieval work?")

    def test_intro_uses_substantive_source_paragraph_when_available(self):
        content = "<p>I personally wanted a holiday.</p><p>Learn how to debug a .NET application by inspecting the threads and locks in its memory dump.</p>"
        self.assertEqual(select_excerpt("I personally wanted a holiday.", content), "Learn how to debug a .NET application by inspecting the threads and locks in its memory dump.")

    def test_topics_ignore_publisher_specialties(self):
        item = enrich_item({"title": "A community picnic", "summary": "Meet the team on Saturday.", "url": "https://example.com/a", "source_title": "AI .NET Security", "source_description": "Architecture and databases"})
        self.assertEqual(item["topics"], ["General"])

    def test_reference_identity_is_not_security_but_authentication_is(self):
        self.assertEqual(classify_topics("Equality in C# with reference identity"), [".NET"])
        self.assertIn("Security", classify_topics("Configure an identity provider with OAuth"))

    def test_critter_stack_override_replaces_personal_intro(self):
        item = enrich_item({"title": "Critter Stack Roadmap Update for November 2026", "url": "https://jeremydmiller.com/2026/11/15/critter-stack-roadmap-update-for-november-2026/", "summary": "I personally want a holiday."})
        self.assertEqual(item["topics"], [".NET", "Architecture"])
        self.assertEqual(item["summary"], "A November 2026 roadmap update for the Critter Stack.")

    def test_duration_preserves_unknown_and_handles_hours(self):
        for value in ("", "0:00", "live", "1:99"):
            self.assertIsNone(duration_seconds(value))
        self.assertEqual(duration_seconds("1:02:03"), 3723)
        self.assertEqual(duration_seconds("1:59"), 119)

    def test_language_uses_declared_audio_language_before_text(self):
        self.assertEqual(detect_language("How to build your first app with the SDK", "pt-BR"), ("pt", False))
        self.assertEqual(detect_language("How to build your first app with the SDK"), ("en", True))
        self.assertEqual(detect_language("MCP SDK"), ("und", False))

    def test_video_formats_do_not_assume_every_long_video_is_a_talk(self):
        self.assertEqual(video_format("A podcast excerpt", "", 90), "clip")
        self.assertEqual(video_format("NDC: building apps", "", 3600), "talk")
        self.assertEqual(video_format(".NET Conf - Day 2", "", 3600), "talk")
        self.assertEqual(video_format("Build a chat app", "", 3600), "other")
        self.assertEqual(video_format("Hands-on .NET workshop", "", 120), "tutorial")

    @patch("youtube.record_feed_health")
    @patch("youtube.get_channel_id", return_value="UC1")
    def test_youtube_uses_full_description_and_audio_language(self, _channel, _health):
        client = MagicMock()
        client.search.return_value.list.return_value.execute.return_value = {"items": [{"id": {"videoId": "abc"}, "snippet": {"title": "Short title", "description": "Truncated...", "publishedAt": "2026-11-17T10:00:00Z"}}]}
        client.videos.return_value.list.return_value.execute.return_value = {"items": [{"id": "abc", "contentDetails": {"duration": "PT10M"}, "snippet": {"title": "How to build a C# app with AI", "description": "The complete tutorial explains how to build your first chat application with .NET.", "defaultAudioLanguage": "es-MX"}}]}
        source = {"id": "demo", "feed": "https://youtube.com/@demo", "website": "https://example.com", "title": "Demo", "description": "", "author": ""}
        item = get_youtube_data(source, client, datetime(2026, 11, 17, 12, tzinfo=timezone.utc))[0]
        self.assertNotIn("Truncated", item["summary"])
        self.assertEqual(item["language"], "es")
        self.assertFalse(item["languageInferred"])
        self.assertEqual(item["durationSeconds"], 600)
        self.assertEqual(item["aiRelevance"], "dotnet")


if __name__ == "__main__":
    unittest.main()
