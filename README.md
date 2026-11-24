# **Building a .NET news aggregator site**

Let's try to build a simple .NET news aggregator site using Python, Hugo and a scheduled Github Action.

This repository contains the site source code. The published code can be found in this another GitHub repository:
- https://github.com/karlospn/dotnetramblings-site-published-code

# **.NET Ramblings site**

The site is published in the following uri:
- https://www.dotnetramblings.com

This site is an automated news aggregator. It fetches news from multiple RSS feeds and YouTube channels, classifies each item by topic, and presents a searchable chronological stream.

The site is automatically updated every 3 hours with the latest news from various RSS feeds. Hugo pages are retained for eight days, while a compact metadata index is retained for 180 days so readers can search and filter the full archive without slowing down the site.

There is also a lot of interesting .NET content on YouTube, so the site contains a dedicated videos section. This section is scheduled to update once every day at 07:15 UTC with recent videos. GitHub Actions schedules are best-effort and can start later than the configured time.

Readers can filter by topic and content type, bookmark stories, hide sources, track read items, and choose a compact layout. These preferences stay in the browser and require no account. The complete site exposes a free RSS feed from the navigation bar.

The AI hub opens with **Building AI with .NET** coverage, with broader AI news available through the Coverage filter. Videos prioritize .NET content and can be filtered by language, duration, and format. Audio language comes from YouTube when supplied; otherwise a conservative text estimate is labeled as estimated, or left unknown. Formats are inferred from descriptions and duration. The AI learning paths include prerequisites, estimated effort, ordered exercises, and review dates.

The **Community Pulse** page collects technical links from selected .NET accounts on Bluesky and Mastodon, up to four external links per day from r/dotnet, and Hacker News stories with an external link, a .NET term in the title, and at least one comment. It covers the past seven days and excludes discussion links already featured in the news or shared by selected accounts. When Reddit and Hacker News discuss the same link or GitHub project, one card links to both threads and appears under either platform filter.

Reddit discussions come from the [Arctic Shift public archive](https://github.com/ArthurHeitmann/arctic_shift/tree/master/api) and can lag behind Reddit. Hacker News stories come from the [Algolia HN Search API](https://hn.algolia.com/api). The search terms are configured in `config/community_pulse_sources.yml`.

The AI topic is a dedicated **AI for .NET Developers** hub. It includes practical subtopics, curated learning paths, and a release radar built from stable GitHub releases for selected .NET AI SDKs and frameworks. Release data is refreshed daily at 08:30 UTC.

# **Contribute**

Suggest a public RSS feed or YouTube channel that regularly publishes content relevant to .NET developers. Related cloud, DevOps, and AI content is welcome when useful to that audience. Check the [existing sources](https://www.dotnetramblings.com/feeds/), then [open a source suggestion](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues/new?template=source-suggestion.yml), or add a `.yml` file to [`data/`](data) with `Feed`, `Title`, and `Website` fields. Include a short `Description` and `Topics` specialties; `Author` is optional. Open a pull request explaining the source's .NET relevance. Submission does not guarantee inclusion or publication of every post.

To suggest a Bluesky or Mastodon account for Community Pulse, [open an issue](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues) with the profile and reason for the suggestion. Community accounts are curated separately; do not add them to `data/`. See the site's [Contribute page](https://www.dotnetramblings.com/contribute/) for the example YAML and full instructions.

## Content maintenance

Story topics use titles and cleaned excerpts, independently of publisher specialties. `config/thumbnail_config.yml` holds the topic vocabulary. `config/content_overrides.yml` accepts canonical story URLs with corrected `summary`, `topics`, `language` (language code), or `videoFormat` (`clip`, `tutorial`, `talk`, `podcast`, `other`). Overrides take precedence during ingestion. Keep summaries faithful to the source; the cleanup pipeline extracts existing text and does not generate claims.

After changing rules or overrides, run `python refresh-content.py` to refresh both retained Markdown pages and the complete metadata archive without fetching or deleting stories. Run `python feeds.py` after editing source descriptions or specialties. Update guided paths in `site/dotnetramblings/data/learning_paths.yml`, including their review dates when reviewed.

Validate with `python -m unittest discover -s tests`, `node --test tests/discovery.test.js`, and `hugo --source site/dotnetramblings --environment development`. Browser previews need an absolute local `--baseURL` so the theme loads its assets and initializes correctly.
