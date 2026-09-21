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

The AI topic is a dedicated **AI for .NET Developers** hub. It includes practical subtopics, curated learning paths, and a release radar built from stable GitHub releases for selected .NET AI SDKs and frameworks. Release data is refreshed daily at 08:30 UTC.

# **Contribute**

Do you create content related to .NET? We're thrilled to welcome you!

Even if your content isn't strictly about .NET, but focuses on software development, cloud computing, AI, or any other tech-related subject, we're excited to feature your posts here!

## How to add your site

### Prerequisite

- A functioning RSS feed or a Youtube Channel that can be accessed via the Internet.

### Enrollment Process

1 - Visit my Github repository: https://github.com/karlospn/building-a-dotnet-news-aggregator-site

2 - The ``/data`` folder contain the current feeds utilized by this site.

3 - Create a new ``yml`` file with the following attributes:
 - ``Feed (required)``: The URL of the RSS feed.
 - ``Title (required)``: The name of your site.
 - ``Website (required)``: The URL of your site.
 - ``Description (optional)``:  A brief description of your site's content.
 - ``Author (optional)``: The name of the site's author.

Here's an example of adding an RSS feed:
```yml
Feed: https://www.mytechramblings.com/index.xml
Title: My technical ramblings
Website: https://www.mytechramblings.com
Description: Technical ramblings from a software engineer
Author: Carlos Pons
```

And here's an example of adding a Youtube channel:
```yml
Feed: https://www.youtube.com/@ChilliCream
Title: ChilliCream
Website: https://chillicream.com/
Description: The Ultimate GraphQL Platform
Author: ChilliCream
```

4 - Open a Pull Request and await our approval.

5 - Your posts will then begin to appear on our site.
