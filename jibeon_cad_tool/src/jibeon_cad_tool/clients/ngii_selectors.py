import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NgiiSelectors:
    login_url: str
    id_login_link_name: str
    search_keyword_selector: str
    download_folder_label: str
    download_watch_dir: str


def load_selectors(path: Path) -> NgiiSelectors:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return NgiiSelectors(**data)
