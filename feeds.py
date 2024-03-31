import yaml  
import os  
import glob
  
feeds = []
folder_path = './data/'
file_paths = glob.glob(os.path.join(folder_path, '*.yml'))  

for file_path in file_paths:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            feeds.append(data)
  
with open('site/dotnetramblings/content/feeds.md', 'w') as file:  
    file.write('---\n')  
    file.write('layout: feeds\n')  
    file.write('feeds:\n')  
    for feed in feeds:          
        if 'Feed' not in feed or 'Title' not in feed: 
            print(f"Missing basic data. Skipped {feed['Feed']}") 
            continue

        file.write(f'  - feed: {feed["Feed"]}\n') 
        file.write(f'    title: {feed["Title"]}\n')   
            
        if 'Website' in feed:  
            file.write(f'    website: {feed["Website"]}\n')             
        if 'Description' in feed:  
            file.write(f'    description: {feed["Description"]}\n')  
        if 'Author' in feed:  
            file.write(f'    author: {feed["Author"]}\n')  
        if 'Language' in feed:  
            file.write(f'    language: {feed["Language"]}\n')  
    
    file.write('---\n')