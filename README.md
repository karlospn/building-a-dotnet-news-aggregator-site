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

The dedicated **Community Pulse** page combines technical links and insights from selected .NET accounts on Bluesky and Mastodon with a small pilot of external links shared in r/dotnet over the last seven days. Search and platform filters cover all posts. Reddit contributes up to four links per day, but Reddit authors are not part of the selected Community Pulse accounts; the Sources page lists the pilot separately for transparency.

The AI topic is a dedicated **AI for .NET Developers** hub. It includes practical subtopics, curated learning paths, and a release radar built from stable GitHub releases for selected .NET AI SDKs and frameworks. Release data is refreshed daily at 08:30 UTC.

# **Contribute**

Suggest a public RSS feed or YouTube channel that regularly publishes content relevant to .NET developers. Related cloud, DevOps, and AI content is welcome when useful to that audience. Check the [existing sources](https://www.dotnetramblings.com/feeds/), then add a `.yml` file to [`data/`](data) with `Feed`, `Title`, and `Website` fields (`Description` and `Author` are optional). Open a pull request explaining the source's .NET relevance. Submission does not guarantee inclusion or publication of every post.

To suggest a Bluesky or Mastodon account for Community Pulse, [open an issue](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues) with the profile and reason for the suggestion. Community accounts are curated separately; do not add them to `data/`. See the site's [Contribute page](https://www.dotnetramblings.com/contribute/) for the example YAML and full instructions.
