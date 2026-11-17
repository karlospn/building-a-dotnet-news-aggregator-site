+++
title = "Contribute"
date = "2024-02-28"
lastmod = "2026-11-17"
informational = true
showReadTime = false
+++

Have a .NET-related blog or YouTube channel to suggest? Contributions from creators and readers are welcome. Sources should regularly publish content relevant to .NET developers; related cloud, DevOps, and AI content is welcome when it is useful to that audience.

## Suggest an RSS feed or YouTube channel

The easiest way is to [open a source suggestion](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues/new?template=source-suggestion.yml) with the feed or channel URL and a short explanation of its relevance. No repository changes are required.

If you prefer to contribute a pull request:

1. Check the existing [Sources](/feeds/) to avoid duplicates.
2. Add one `.yml` file for the source in the repository's [`data/` folder](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/tree/main/data), using the existing files as examples. Include `Feed` (the public RSS URL or YouTube channel URL), `Title` (the source name), and `Website` (the source's website URL). Add a short `Description` and a `Topics` list describing its usual specialties; `Author` is optional. Specialties describe the source and do not determine each story's tags.
3. Open a pull request with a brief explanation of the source's relevance to .NET developers.

For example:

```yml
Feed: https://www.mytechramblings.com/index.xml
Title: My technical ramblings
Website: https://www.mytechramblings.com/
Description: Technical ramblings from a software engineer
Topics: [.NET, Azure, AWS]
Author: Carlos Pons
```

To propose an account for [Community Pulse](/community/), open a [GitHub issue](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues) with its Bluesky or Mastodon profile and why its posts would be relevant. Community accounts are curated separately from the `data/` feed files; do not add them there.

Suggestions are reviewed for fit and reliability. Submission does not guarantee inclusion or publication of every post.

## Report a content correction

[Open an issue](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues/new) with the original story URL and the incorrect excerpt, topic, language, or video format. Include your proposed correction so it can be reviewed.
