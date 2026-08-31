from pathlib import Path
from unittest.mock import MagicMock

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from jibeon_cad_tool.clients.ngii_selectors import NgiiSelectors
from jibeon_cad_tool.clients.ngii_web_client import LOGIN_WAIT_TIMEOUT_MS, NgiiWebClient
from jibeon_cad_tool.models import CoordSystem, MapScale, ParcelSearchResult


def make_selectors() -> NgiiSelectors:
    return NgiiSelectors(
        login_url="https://map.ngii.go.kr",
        id_login_link_name="아이디 로그인 ...",
        search_keyword_selector="#totalSearchKeyword",
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


def test_login_opens_popup_and_waits_for_user_to_complete_login():
    client = NgiiWebClient(username="user1", password="pass1", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    popup = MagicMock()
    popup.wait_for_event.return_value = None
    page.expect_popup.return_value.__enter__.return_value.value = popup

    client._login(page)

    page.goto.assert_called_once_with("https://map.ngii.go.kr")
    page.get_by_role.assert_any_call("link", name="로그인")
    page.get_by_role.assert_any_call("link", name="아이디 로그인 ...")
    popup.wait_for_event.assert_called_once_with("close", timeout=LOGIN_WAIT_TIMEOUT_MS)


def test_login_raises_when_user_never_completes_login():
    client = NgiiWebClient(username="user1", password="pass1", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    popup = MagicMock()
    popup.wait_for_event.side_effect = PlaywrightTimeoutError("timed out")
    page.expect_popup.return_value.__enter__.return_value.value = popup

    with pytest.raises(RuntimeError):
        client._login(page)


# NgiiWebClient는 이제 도엽번호를 실제 GeoPackage 인덱스(data/*.gpkg)에서 직접 조회하므로,
# 예전 GeoJSON fixture 기반 sheet_features 인자는 더 이상 쓰이지 않는다 — pipeline.py의
# 공개 시그니처를 바꾸지 않기 위해 매개변수 자체는 남아있어 빈 리스트로 채운다.
SHEET_FEATURES_UNUSED: list[dict] = []


def make_search_result() -> ParcelSearchResult:
    # 실제 국토지리정보원 도엽 인덱스(data/*.gpkg)로 조회했을 때 도엽번호 "37615020"
    # (1:5,000, 대부020)이 나오는 것으로 실 계정 확인된 좌표 — 경기 화성시 송산면 사강리 671
    return ParcelSearchResult(
        pnu="4159132021106710000", address="경기 화성시 만세구 송산면 사강리 671", x=176453.942652644, y=512757.609257195,
        coord_system=CoordSystem.GRS80_MID,
    )


def test_download_topo_mock_mode_writes_stub(tmp_path):
    client = NgiiWebClient(use_mock=True)
    output_path = str(tmp_path / "topo.txt")

    result = client.download_topo(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SHEET_FEATURES_UNUSED, output_path
    )

    assert result.file_path == output_path
    content = open(output_path, encoding="utf-8").read()
    assert "TOPO" in content


def test_download_topo_real_mode_logs_in_searches_and_downloads(monkeypatch, tmp_path):
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    output_path = str(tmp_path / "out.tif")
    selectors = make_selectors()
    selectors.download_watch_dir = str(watch_dir)

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=selectors)
    page = MagicMock()
    popup = MagicMock()
    popup.wait_for_event.return_value = None
    page.expect_popup.return_value.__enter__.return_value.value = popup
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )

    def write_downloaded_file(*_args, **_kwargs):
        (watch_dir / "downloaded.tif").write_bytes(b"dummy-tif-bytes")

    monkeypatch.setattr("time.sleep", lambda _seconds: write_downloaded_file())

    result = client.download_topo(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SHEET_FEATURES_UNUSED, output_path
    )

    assert result is not None
    assert Path(output_path).read_bytes() == b"dummy-tif-bytes"
    page.locator.assert_any_call("#totalSearchKeyword")
    page.locator.return_value.fill.assert_any_call("37615020")
    page.get_by_text.assert_any_call("37615020", exact=True)
    page.get_by_role.assert_any_call("button", name="수치지도", exact=False)
    page.get_by_text.assert_any_call("수치지형도(DXF파일)", exact=False)
    page.get_by_role.assert_any_call("checkbox")
    page.get_by_role.assert_any_call("button", name="다운로드", exact=True)


def test_download_ortho_real_mode_returns_downloaded_file(monkeypatch, tmp_path):
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    output_path = str(tmp_path / "out_ortho.tif")
    (watch_dir / "already_there.tif").write_bytes(b"pre-existing-file-not-the-download")
    selectors = make_selectors()
    selectors.download_watch_dir = str(watch_dir)

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=selectors)
    page = MagicMock()
    popup = MagicMock()
    popup.wait_for_event.return_value = None
    page.expect_popup.return_value.__enter__.return_value.value = popup
    page.get_by_role.return_value.filter.return_value.count.return_value = 1
    page.get_by_role.return_value.filter.return_value.nth.return_value.inner_text.return_value = "촬영 2025"
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )

    def write_downloaded_file(*_args, **_kwargs):
        (watch_dir / "downloaded_ortho.tif").write_bytes(b"dummy-ortho-bytes")

    monkeypatch.setattr("time.sleep", lambda _seconds: write_downloaded_file())

    result = client.download_ortho(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SHEET_FEATURES_UNUSED, output_path,
        poll_interval_seconds=0.01, timeout_seconds=5.0,
    )

    assert result is not None
    assert Path(output_path).read_bytes() == b"dummy-ortho-bytes"


def test_download_ortho_real_mode_returns_none_on_timeout(monkeypatch, tmp_path):
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    output_path = str(tmp_path / "out_ortho.tif")
    selectors = make_selectors()
    selectors.download_watch_dir = str(watch_dir)

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=selectors)
    page = MagicMock()
    popup = MagicMock()
    popup.wait_for_event.return_value = None
    page.expect_popup.return_value.__enter__.return_value.value = popup
    page.get_by_role.return_value.filter.return_value.count.return_value = 1
    page.get_by_role.return_value.filter.return_value.nth.return_value.inner_text.return_value = "촬영 2025"
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    times = iter([0.0, 0.5, 1.5])
    monkeypatch.setattr("time.monotonic", lambda: next(times))

    result = client.download_ortho(
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SHEET_FEATURES_UNUSED, output_path,
        poll_interval_seconds=0.01, timeout_seconds=1.0,
    )

    assert result is None
    assert not Path(output_path).exists()


def test_select_most_recent_ortho_item_picks_highest_year():
    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=make_selectors())
    page = MagicMock()
    items = page.get_by_role.return_value.filter.return_value
    items.count.return_value = 3
    texts = {
        0: "수도권북부1권역 25cm 촬영 2022위치 인천/37611100",
        1: "수도권북부1권역 25cm 촬영 2025위치 인천/37611100",
        2: "수도권북부1권역 25cm 촬영 2019위치 인천/37611100",
    }
    items.nth.side_effect = lambda i: MagicMock(inner_text=MagicMock(return_value=texts[i]))

    selected = client._select_most_recent_ortho_item(page, "37611100")

    assert selected.inner_text() == texts[1]


def test_download_topo_real_mode_raises_on_timeout(monkeypatch, tmp_path):
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    output_path = str(tmp_path / "out.tif")
    selectors = make_selectors()
    selectors.download_watch_dir = str(watch_dir)

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=selectors)
    page = MagicMock()
    popup = MagicMock()
    popup.wait_for_event.return_value = None
    page.expect_popup.return_value.__enter__.return_value.value = popup
    playwright_context = MagicMock()
    playwright_context.new_page.return_value = page
    monkeypatch.setattr(
        "jibeon_cad_tool.clients.ngii_web_client.sync_playwright",
        lambda: _FakePlaywrightCM(playwright_context),
    )
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    times = iter([0.0, 100.0])
    monkeypatch.setattr("time.monotonic", lambda: next(times))

    with pytest.raises(RuntimeError):
        client.download_topo(
            make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SHEET_FEATURES_UNUSED, output_path
        )


def test_constructor_overrides_download_folder_label_and_watch_dir():
    client = NgiiWebClient(
        username="u",
        password="p",
        use_mock=True,
        download_folder_label="MyFolder",
        download_watch_dir="/custom/watch/dir",
    )

    assert client.selectors.download_folder_label == "MyFolder"
    assert client.selectors.download_watch_dir == "/custom/watch/dir"


def test_constructor_without_override_keeps_config_defaults():
    client = NgiiWebClient(username="u", password="p", use_mock=True)

    assert client.selectors.download_folder_label != "MyFolder"
    assert client.selectors.download_watch_dir != "/custom/watch/dir"


def test_constructor_empty_string_override_is_ignored():
    client = NgiiWebClient(
        username="u", password="p", use_mock=True, download_folder_label="", download_watch_dir=""
    )
    default_client = NgiiWebClient(username="u", password="p", use_mock=True)

    assert client.selectors.download_folder_label == default_client.selectors.download_folder_label
    assert client.selectors.download_watch_dir == default_client.selectors.download_watch_dir


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
