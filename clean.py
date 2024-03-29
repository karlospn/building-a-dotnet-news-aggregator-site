import os  
from datetime import datetime, timedelta 
import shutil 
  
base_path = "./site/dotnetramblings/content/post"  
for dir_name in os.listdir(base_path):  
    dir_path = os.path.join(base_path, dir_name)  
    if os.path.isdir(dir_path):  
        dir_time = datetime.strptime(dir_name, "%d_%m_%Y")  
        if dir_time < datetime.now() - timedelta(days=7):  
            shutil.rmtree(dir_path)  
