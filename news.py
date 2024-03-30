import yaml
import feedparser
import os
import glob
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from urllib.parse import urlparse  

def calculate_thumbail_image(title, description):
    s1 = title.lower()  
    s2 = description.tolower()

    if 'dotnet' in s1 or '.net' in s1 or 'c#' in s1 or 'dotnet' in s2 or '.net' in s2 or 'c#' in s2:  
        return 'images/dotnet.png'  
    elif 'azure' in s1 or 'azure' in s2:  
        return 'images/azure.png'  
    elif 'amazon' in s1 or 'aws' in s1 or 'amazon' in s2 or 'aws' in s2:  
        return 'images/aws.png'
    elif 'iac' in s1 or 'terraform' in s1 or 'iac' in s2 or 'terraform' in s2:  
        return 'images/iac.png'  
    elif 'container' in s1 or 'docker' in s1 or 'container' in s2 or 'docker' in s2:  
        return 'images/container.png'  
    elif 'devops' in s1 or 'ci/cd' in s1 or 'devops' in s2 or 'ci/cd' in s2:  
        return 'images/devops.png' 
    else:  
        return 'images/dotnet.png'  

def get_website_name(url):  
    parsed_uri = urlparse(url)  
    domain = '{uri.netloc}'.format(uri=parsed_uri)  
    return domain.split('.')[0]  

def parse_yml_files(file_paths):
    rss_urls = []
    for file_path in file_paths:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            rss_urls.append(data['Feed'])
    return rss_urls

def fetch_rss_feeds(rss_urls):
    news_items = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)

            today = datetime.now()
            # today = datetime.now - timedelta(4) 
            today = today.replace(hour=0, minute=0, second=0, microsecond=0)  

            for entry in feed.entries:
                post_date = dateparser.parse(entry.published)
            
                if post_date.date() != today.date():
                    continue

                if any(item['title'] == entry.title for item in news_items):
                    continue

                news_items.append({
                    'title': entry.title,
                    'url': entry.link,
                    'date': post_date.isoformat(),
                    'summary': entry.summary
                })
        except Exception as e:
            print(f"Failed to parse feed {url}: {e}")
            
    news_items = sorted(news_items, key=lambda x: x['date'], reverse=True)  
    return news_items

def escape_field(text):
    text = text.replace('"', '\\"')
    return text

def convert_rss_data_to_md(rss_entry):
    title = escape_field(rss_entry["title"])
    link = rss_entry["url"]
    published = rss_entry.get("date", "")

    summary = rss_entry["summary"]
    soup = BeautifulSoup(summary, 'html.parser')
    summary = soup.get_text()
    image = calculate_thumbail_image(title, summary)

    site_name = get_website_name(link)

    print(f"{title}")
    template = f"""---
title: "{title}"
date: {published}
link: {link}
showShare: false
showReadTime: false
thumbnail: {image}
tags: ["{site_name}"]
---
{summary}

- Link to article: {link}"""
    return template


def generate_hugo_content(news_items):
    count = 0
    for item in news_items:
        md = convert_rss_data_to_md(item)
        today = datetime.today().strftime("%d_%m_%Y")
        # today = datetime.today() - timedelta(4)
        # today = today.strftime("%d_%m_%Y")
        directory = f"site/dotnetramblings/content/post/{today}"

        if not os.path.exists(directory):
                os.makedirs(directory)

        with open(f"{directory}/{today}_{count}.md", "w", encoding='utf-8') as file:
             file.write(md)
        count += 1

def main():
    folder_path = './data/'
    file_paths = glob.glob(os.path.join(folder_path, '*.yml'))
    rss_urls = parse_yml_files(file_paths)
    news_items = fetch_rss_feeds(rss_urls)
    generate_hugo_content(news_items)

if __name__ == "__main__":
    main()