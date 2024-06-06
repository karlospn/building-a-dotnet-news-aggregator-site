+++
title = "Contribute"
date = "2024-02-28"
+++

Do you create content related to .NET? We're thrilled to welcome you!

Even if your content isn't strictly about .NET, but focuses on software development, cloud computing, AI, or any other tech-related subject, we're excited to feature your posts here!

# How to add your site

## Prerequisite

- A functioning RSS feed or a Youtube Channel that can be accessed via the Internet.

## Enrollment Process

1 - Visit my Github repository: https://github.com/karlospn/building-a-dotnet-news-aggregator-site

2 - The ``/data`` folder contain the current feeds utilized by this site.

3 - Create a new ``yml`` file with the following attributes:
 - ``Feed (required)``: The URL of the RSS feed or the Youtube channel.
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


