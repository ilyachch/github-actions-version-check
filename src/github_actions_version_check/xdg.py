import os
from pathlib import Path

APP_DIR_NAME = 'github_actions_version_check'


def _xdg_home(env_var: str, fallback_dir: str) -> Path:
    value = os.getenv(env_var)
    if value:
        return Path(value).expanduser()
    return Path.home() / fallback_dir


def cache_dir() -> Path:
    return _xdg_home('XDG_CACHE_HOME', '.cache') / APP_DIR_NAME


def config_dir() -> Path:
    return _xdg_home('XDG_CONFIG_HOME', '.config') / APP_DIR_NAME


def data_dir() -> Path:
    return _xdg_home('XDG_DATA_HOME', '.local/share') / APP_DIR_NAME
