import os
import glob
from datetime import datetime, timedelta
from urllib.parse import urlparse  
from urllib.parse import urlparse, parse_qs, unquote
import os
import time
from datetime import datetime
from googleapiclient.discovery import build  
from common import parse_yml_files, convert_rss_data_to_md


def get_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    youtube = build('youtube', 'v3', developerKey=api_key)  
    return youtube

def is_youtube_channel(url):  
    parsed_url = urlparse(url)  
    if parsed_url.netloc != 'www.youtube.com':  
        return False  
    return True  


def get_youtube_data(data):
    news_items = []
    youtube = get_youtube_client()
    channel_id = get_channel_id(data["feed"], youtube)

    if channel_id is None:
        print("Your youtube url is not valid")
        return news_items

    res = youtube.search().list(part='snippet', channelId=channel_id, type='video', order='date', maxResults=25).execute()  
    yesterday = datetime.now() - timedelta(days=1)  
    
    for video in res["items"]:      
        published_at = datetime.strptime(video['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")  
        if published_at.date() == yesterday.date():  
            news_items.append({  
                'title': video['snippet']['title'],  
                'url': 'https://www.youtube.com/watch?v=' + video['id']['videoId'],  
                'date': video['snippet']['publishedAt'],  
                'summary': video['snippet']['description'],
                'website': data['website']  
            })  
    return news_items

def get_channel_id(url, youtube):  
    parsed_url = urlparse(url)  
    if parsed_url.netloc not in ['www.youtube.com', 'youtube.com']:  
        return None  
  
    if parsed_url.path == '/user/':  
        username = parsed_url.path.split('/')[2]  
        request = youtube.channels().list(  
            part="id",  
            forUsername=username  
        )  
        response = request.execute()  
        if response['items']:  
            return response['items'][0]['id']  
  
    if parsed_url.path == '/channel/':  
        return parsed_url.path.split('/')[2]  
  
    if parsed_url.path == '/watch':  
        video_id = parse_qs(parsed_url.query)['v'][0]  
        request = youtube.videos().list(  
            part="snippet",  
            id=video_id  
        )  
        response = request.execute()  
        if response['items']:  
            return response['items'][0]['snippet']['channelId']  
  
    if parsed_url.path.startswith('/@'):  
        res = youtube.search().list(q=unquote(parsed_url.path[2:]), type='channel', part='id').execute()  
        if res['items']:  
            return res['items'][0]['id']['channelId']  
  
    return None 

def fetch_youtube_channels(data):
    video_items = []
    for d in data:
        try:
            if is_youtube_channel(d['feed']):
                 video_items.append(get_youtube_data(d)) 
                 time.sleep(1)   
            else:
               continue

        except Exception as e:
            print(f"Failed to parse feed {d}: {e}")

    video_items = [element for element in video_items if element != []]   
    video_items = sorted([item for sublist in video_items for item in sublist], key=lambda x: datetime.strptime(x['date'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
    return video_items

def generate_hugo_content(video_items):
    count = 0
    for item in video_items:
        md = convert_rss_data_to_md(item)        
        yesterday = datetime.today() - timedelta(days=1)
        yesterday = yesterday.strftime("%d_%m_%Y")
        directory = f"site/dotnetramblings/content/videos/{yesterday}"

        if not os.path.exists(directory):
                os.makedirs(directory)

        with open(f"{directory}/{yesterday}_{count}.md", "w", encoding='utf-8') as file:
             file.write(md)

        count += 1

def main():
    folder_path = './data/'
    file_paths = glob.glob(os.path.join(folder_path, '*.yml'))
    data = parse_yml_files(file_paths)
    video_items = fetch_youtube_channels(data)
    generate_hugo_content(video_items)

if __name__ == "__main__":
    main()