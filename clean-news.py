import os  
from datetime import datetime, timedelta 
import shutil 
  
base_paths = ["./site/dotnetramblings/content/post"]

for base_path in base_paths:  
    for dir_name in os.listdir(base_path):  
        dir_path = os.path.join(base_path, dir_name)  
        if os.path.isdir(dir_path):  
            dir_time = datetime.strptime(dir_name, "%d_%m_%Y")  
            if dir_time < datetime.now() - timedelta(days=8):  
                shutil.rmtree(dir_path)  
            if dir_time == datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):  
                shutil.rmtree(dir_path)  