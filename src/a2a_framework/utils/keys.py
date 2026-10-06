import os
import json
from pathlib import Path

# Function to set api keys. We want all api keys in one place. Useful when we want to remove them 
def set_api_keys(config):

    key_config = None
    with open(Path(config).resolve(),"rb") as file:
        key_config = json.load(file)["path_config"]["key"]
    

    if isinstance(key_config,str):
        os.environ["LLM_API_KEY"] = key_config

    if isinstance(key_config,dict):
        for keys,values in key_config.items():
            os.environ[keys] = values