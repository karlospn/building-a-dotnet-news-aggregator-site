+++
title = "Contribute"
date = "2024-02-28"
+++

Have a .NET-related blog or YouTube channel to suggest? Contributions from creators and readers are welcome. Sources should regularly publish content relevant to .NET developers; related cloud, DevOps, and AI content is welcome when it is useful to that audience.

## Suggest an RSS feed or YouTube channel

1. Check the existing [Sources](/feeds/) to avoid duplicates.
2. Add one `.yml` file for the source in the repository's [`data/` folder](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/tree/main/data), using the existing files as examples. Include `Feed` (the public RSS URL or YouTube channel URL), `Title` (the source name), and `Website` (the source's website URL). `Description` and `Author` are optional.
3. Open a pull request with a brief explanation of the source's relevance to .NET developers.

For example:

```yml
Feed: https://www.mytechramblings.com/index.xml
Title: My technical ramblings
Website: https://www.mytechramblings.com/
Description: Technical ramblings from a software engineer
Author: Carlos Pons
```

To propose an account for [Community Pulse](/community/), open a [GitHub issue](https://github.com/karlospn/building-a-dotnet-news-aggregator-site/issues) with its Bluesky or Mastodon profile and why its posts would be relevant. Community accounts are curated separately from the `data/` feed files; do not add them there.

Suggestions are reviewed for fit and reliability. Submission does not guarantee inclusion or publication of every post.
