# tests/test_ngii_selectors.py
from pathlib import Path

from jibeon_cad_tool.clients.ngii_selectors import load_selectors

CONFIG_PATH = Path(__file__).parent.parent / "config" / "ngii_selectors.json"


def test_load_selectors_reads_all_fields_from_json():
    selectors = load_selectors(CONFIG_PATH)

    assert selectors.login_url == "https://map.ngii.go.kr"
    assert selectors.id_login_link_name
    assert selectors.search_keyword_selector == "#totalSearchKeyword"
    assert selectors.map_pin_click_selector
    assert selectors.map_click_count == 2
    assert selectors.download_folder_label
    assert selectors.download_watch_dir


def test_load_selectors_from_custom_path(tmp_path):
    custom_config = tmp_path / "custom_selectors.json"
    custom_config.write_text(
        '{"login_url": "https://example.com", "id_login_link_name": "a",'
        ' "search_keyword_selector": "#kw",'
        ' "map_pin_click_selector": ".pin", "map_click_count": 2,'
        ' "download_folder_label": "e", "download_watch_dir": "f"}',
        encoding="utf-8",
    )

    selectors = load_selectors(custom_config)

    assert selectors.login_url == "https://example.com"
    assert selectors.map_click_count == 2
