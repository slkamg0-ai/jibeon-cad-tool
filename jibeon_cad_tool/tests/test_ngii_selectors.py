from pathlib import Path

from jibeon_cad_tool.clients.ngii_selectors import load_selectors

CONFIG_PATH = Path(__file__).parent.parent / "config" / "ngii_selectors.json"


def test_load_selectors_reads_all_fields_from_json():
    selectors = load_selectors(CONFIG_PATH)

    assert selectors.login_url == "https://map.ngii.go.kr"
    assert selectors.catalog_url == "https://map.ngii.go.kr/pd/ctlsSvc/ctlsSvc.do"
    assert selectors.login_trigger_selector
    assert selectors.username_selector
    assert selectors.password_selector
    assert selectors.login_submit_selector
    assert selectors.sido_select_selector
    assert selectors.scale_select_selector
    assert selectors.sheet_no_input_selector
    assert selectors.search_button_selector
    assert selectors.cart_add_selector
    assert selectors.request_submit_selector
    assert selectors.download_link_selector
    assert selectors.request_status_selector


def test_load_selectors_from_custom_path(tmp_path):
    custom_config = tmp_path / "custom_selectors.json"
    custom_config.write_text(
        '{"login_url": "https://example.com", "login_trigger_selector": "a",'
        ' "username_selector": "b", "password_selector": "c", "login_submit_selector": "d",'
        ' "catalog_url": "https://example.com/catalog", "sido_select_selector": "e",'
        ' "scale_select_selector": "f", "sheet_no_input_selector": "g", "search_button_selector": "h",'
        ' "cart_add_selector": "i", "request_submit_selector": "j", "download_link_selector": "k",'
        ' "request_status_selector": "l"}',
        encoding="utf-8",
    )

    selectors = load_selectors(custom_config)

    assert selectors.login_url == "https://example.com"
    assert selectors.catalog_url == "https://example.com/catalog"
