import yaml
from bs4 import BeautifulSoup
from urllib.parse import urlparse  

def parse_yml_files(file_paths):
    rss_data = []
    for file_path in file_paths:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            
            if 'Feed' not in data or 'Title' not in data or 'Website' not in data: 
                print(f"Missing basic data. Skipped Feed.") 
                continue

            rss_data.append({
                'feed': data['Feed'],
                'website': data['Website']
            })

    return rss_data

def convert_rss_data_to_md(rss_entry):
    title = _escape_field(rss_entry["title"])
    link = rss_entry["url"]
    published = rss_entry.get("date", "")

    summary = rss_entry["summary"]
    soup = BeautifulSoup(summary, 'html.parser')
    summary = soup.get_text()
    image = _calculate_thumbail_image(title, summary)
    site_name = _get_website_name(rss_entry['website'])

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


def _escape_field(text):
    text = text.replace('"', '\\"')
    return text

def _calculate_thumbail_image(title, description):  
    s1 = title.lower()    
    s2 = description.lower() 
  
    with open('config/thumbnail_config.yml', 'r') as file:  
        config = yaml.safe_load(file)  
    
    for item in config['keywords']:  
        if any(keyword in s1 or keyword in s2 for keyword in item['keywords']):  
            return item['image']  
  
    return config['default_image']  


def _get_website_name(url):    
    parsed_uri = urlparse(url)    
    domain_parts = '{uri.netloc}'.format(uri=parsed_uri).split('.')    
   
    if domain_parts[0] == 'www':    
        domain_parts = domain_parts[1:]    
    
    domain = '.'.join(domain_parts)    
    path = '{uri.path}'.format(uri=parsed_uri)  
      
    if path.endswith('/'):  
        path = path[:-1]  
  
    if path != '/':    
        domain += path 
 
    return domain 