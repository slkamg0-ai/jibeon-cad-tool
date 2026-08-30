from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jibeon_cad_tool.clients.ngii_selectors import NgiiSelectors
from jibeon_cad_tool.clients.ngii_web_client import NgiiWebClient
from jibeon_cad_tool.models import CoordSystem, MapScale, ParcelSearchResult


def make_selectors() -> NgiiSelectors:
    return NgiiSelectors(
        login_url="https://map.ngii.go.kr",
        id_login_link_name="아이디 로그인 ...",
        username_placeholder="아이디 placeholder",
        password_placeholder="비밀번호 placeholder",
        login_submit_button_name="회원 들어가기",
        search_keyword_selector="#totalSearchKeyword",
        map_pin_click_selector=".ol-unselectable > div:nth-child(3)",
        map_click_count=2,
        download_folder_label="Work",
        download_watch_dir="/tmp/ngii-downloads",
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


def test_login_opens_popup_and_fills_credentials():
    client = NgiiWebClient(username="user1", password="pass1", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    popup = MagicMock()
    popup.get_by_placeholder.return_value.is_visible.return_value = True
    page.expect_popup.return_value.__enter__.return_value.value = popup

    client._login(page)

    page.goto.assert_called_once_with("https://map.ngii.go.kr")
    page.get_by_role.assert_any_call("link", name="로그인")
    popup.get_by_placeholder.assert_any_call("아이디 placeholder")
    popup.get_by_placeholder.assert_any_call("비밀번호 placeholder")
    popup.get_by_placeholder.return_value.fill.assert_any_call("user1")
    popup.get_by_placeholder.return_value.fill.assert_any_call("pass1")
    popup.get_by_role.assert_any_call("button", name="회원 들어가기")
    popup.close.assert_called_once()


def test_login_raises_when_login_form_never_becomes_visible():
    client = NgiiWebClient(username="user1", password="pass1", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    popup = MagicMock()
    popup.get_by_placeholder.return_value.is_visible.return_value = False
    page.expect_popup.return_value.__enter__.return_value.value = popup

    with pytest.raises(RuntimeError):
        client._login(page)


SAMPLE_FEATURES = [
    {
        "type": "Feature",
        "properties": {"scale": "1:5000", "sheet_no": "358051"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[198000.0, 453000.0], [199000.0, 453000.0], [199000.0, 454000.0], [198000.0, 454000.0], [198000.0, 453000.0]]],
        },
    }
]


def make_search_result() -> ParcelSearchResult:
    return ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198500.0, y=453500.0,
        coord_system=CoordSystem.GRS80_MID,
    )


def test_download_topo_mock_mode_writes_stub(tmp_path):
    client = NgiiWebClient(use_mock=True)
    output_path = str(tmp_path / "topo.txt")

    result = client.download_topo(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path
    )

    assert result.file_path == output_path
    content = open(output_path, encoding="utf-8").read()
    assert "TOPO" in content


def test_download_topo_real_mode_logs_in_searches_and_downloads(monkeypatch, tmp_path):
    downloaded_file = tmp_path / "downloaded.tif"
    downloaded_file.write_bytes(b"dummy-tif-bytes")
    output_path = str(tmp_path / "out.tif")

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    page.locator.return_value.is_visible.return_value = True
    download = MagicMock()
    download.path.return_value = str(downloaded_file)
    page.expect_download.return_value.__enter__.return_value.value = download
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )

    result = client.download_topo(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path
    )

    assert result is not None
    assert Path(output_path).read_bytes() == b"dummy-tif-bytes"
    page.fill.assert_any_call("#sheet-no", "358051")
    page.click.assert_any_call("#search")
    page.click.assert_any_call("#cart-add")
    page.click.assert_any_call("#request-submit")


def test_download_ortho_real_mode_polls_until_ready(monkeypatch, tmp_path):
    downloaded_file = tmp_path / "downloaded_ortho.tif"
    downloaded_file.write_bytes(b"dummy-ortho-bytes")
    output_path = str(tmp_path / "out_ortho.tif")

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    # First is_visible() call happens inside _login (must be True to pass login);
    # the next two are the polling loop's "is the download ready?" checks (not ready, then ready).
    page.locator.return_value.is_visible.side_effect = [True, False, True]
    download = MagicMock()
    download.path.return_value = str(downloaded_file)
    page.expect_download.return_value.__enter__.return_value.value = download
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    result = client.download_ortho(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path,
        poll_interval_seconds=0.01, timeout_seconds=1.0,
    )

    assert result is not None
    assert Path(output_path).read_bytes() == b"dummy-ortho-bytes"


def test_download_ortho_real_mode_returns_none_on_timeout(monkeypatch, tmp_path):
    output_path = str(tmp_path / "out_ortho.tif")

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    # First is_visible() call is the login check (True = login form found, login succeeds).
    # The next two are the polling loop's "is the download ready?" checks — always not ready.
    page.locator.return_value.is_visible.side_effect = [True, False, False]
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    # start=0.0, loop-iteration-1 check=0.5 (0.5-0.0<1.0 → keep polling),
    # loop-iteration-2 check=1.5 (1.5-0.0>=1.0 → timeout, return None)
    times = iter([0.0, 0.5, 1.5])
    monkeypatch.setattr("time.monotonic", lambda: next(times))

    result = client.download_ortho(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path,
        poll_interval_seconds=0.01, timeout_seconds=1.0,
    )

    assert result is None
    assert not Path(output_path).exists()


class _FakePlaywrightCM:
    def __init__(self, browser_context):
        self._browser_context = browser_context

    def __enter__(self):
        outer = self

        class _PW:
            class chromium:
                @staticmethod
                def launch(**_kwargs):
                    return outer._browser_context

        return _PW()

    def __exit__(self, *_args):
        return False
