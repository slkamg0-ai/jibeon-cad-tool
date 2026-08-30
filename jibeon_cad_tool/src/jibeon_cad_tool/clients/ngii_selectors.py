import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NgiiSelectors:
    login_url: str
    login_trigger_selector: str
    username_selector: str
    password_selector: str
    login_submit_selector: str
    catalog_url: str
    scale_select_selector: str
    sheet_no_input_selector: str
    search_button_selector: str
    cart_add_selector: str
    request_submit_selector: str
    download_link_selector: str


def load_selectors(path: Path) -> NgiiSelectors:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return NgiiSelectors(**data)
