import toml
from typing import Dict

def load_config_file(config_file_path: str) -> Dict:
    merged_data = {}

    config = toml.load(open(config_file_path))
    include = config["include"]
    file_paths_dict = {key: value for key, value in include.items()}
    for name, file_path in file_paths_dict.items():
        data = load_config_file(file_path)
        if name == "_":
            merged_data.update(data)
        else:
            merged_data[name] = data
    config.pop("include")
    return merged_data

