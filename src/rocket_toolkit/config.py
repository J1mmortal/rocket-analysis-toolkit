import os
import json
from importlib import resources

# Where the user-editable config.json will live:
CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
_config_cache = None


def _load_default_config():
    with resources.files("rocket_toolkit").joinpath("default_config.json").open(
        "r", encoding="utf-8"
    ) as f:
        return json.load(f)


def load_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not os.path.exists(CONFIG_FILE):
        default_config = _load_default_config()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        print("\nNo config.json found, wrote default config to current directory")
        _config_cache = default_config
        return _config_cache

    with open(CONFIG_FILE, encoding="utf-8") as f:
        print("\nConfig file found successfully")
        _config_cache = json.load(f)
        return _config_cache


def save_config(cfg):
    global _config_cache
    _config_cache = cfg
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(_config_cache, f, indent=2)
