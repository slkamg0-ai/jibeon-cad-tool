from unittest.mock import MagicMock

import pytest

from jibeon_cad_tool.clients.ngii_selectors import NgiiSelectors
from jibeon_cad_tool.clients.ngii_web_client import NgiiWebClient


def make_selectors() -> NgiiSelectors:
    return NgiiSelectors(
        login_url="https://map.ngii.go.kr",
        login_trigger_selector="#login-trigger",
        username_selector="#username",
        password_selector="#password",
        login_submit_selector="#login-submit",
        catalog_url="https://map.ngii.go.kr/pd/ctlsSvc/ctlsSvc.do",
        sido_select_selector="#sido",
        scale_select_selector="#scale",
        sheet_no_input_selector="#sheet-no",
        search_button_selector="#search",
        cart_add_selector="#cart-add",
        request_submit_selector="#request-submit",
        download_link_selector="#download-link",
        request_status_selector="#status",
    )


def test_defaults_to_mock_when_no_credentials(monkeypatch):
    monkeypatch.delenv("NGII_USERNAME", raising=False)
    monkeypatch.delenv("NGII_PASSWORD", raising=False)

    client = NgiiWebClient()

    assert client.use_mock is True


def test_does_not_default_to_mock_when_credentials_present(monkeypatch):
    monkeypatch.setenv("NGII_USERNAME", "user1")
    monkeypatch.setenv("NGII_PASSWORD", "pass1")

    client = NgiiWebClient()

    assert client.use_mock is False


def test_login_fills_credentials_and_clicks_submit():
    client = NgiiWebClient(username="user1", password="pass1", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    page.locator.return_value.is_visible.return_value = True

    client._login(page)

    page.goto.assert_called_once_with("https://map.ngii.go.kr")
    page.fill.assert_any_call("#username", "user1")
    page.fill.assert_any_call("#password", "pass1")
    page.click.assert_any_call("#login-submit")


def test_login_raises_when_login_form_never_becomes_visible():
    client = NgiiWebClient(username="user1", password="pass1", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    page.locator.return_value.is_visible.return_value = False

    with pytest.raises(RuntimeError):
        client._login(page)
