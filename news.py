import yaml
import feedparser
import os
import glob
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from youtube import is_youtube_channel
from common import parse_yml_files, convert_rss_data_to_md

def get_rss_data(data):
    
    news_items = []  
    feed = feedparser.parse(data['feed'])
    today = datetime.now()
    # today = datetime.now() - timedelta(7) 
    # today = today.replace(hour=0, minute=0, second=0, microsecond=0)  

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
            'summary': entry.summary,
            'website': data['website']
        })
    return news_items 

def fetch_rss_feeds(rss_data):
    news_items = []
    for data in rss_data:
        try:
            if is_youtube_channel(data['feed']):
                continue
            else:
                news_items.append(get_rss_data(data))    

        except Exception as e:
            print(f"Failed to parse feed {data}: {e}")

    news_items = [element for element in news_items if element != []]
    news_items = sorted([item for sublist in news_items for item in sublist], key=lambda x: x['date'], reverse=True)           
    return news_items



def generate_hugo_content(news_items):
    count = 0
    for item in news_items:
        md = convert_rss_data_to_md(item)
        today = datetime.today().strftime("%d_%m_%Y")
        # today = datetime.today() - timedelta(7)
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
    rss_data = parse_yml_files(file_paths)
    news_items = fetch_rss_feeds(rss_data)
    generate_hugo_content(news_items)

if __name__ == "__main__":
    main()