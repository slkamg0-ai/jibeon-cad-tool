import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..models import CoordSystem, MapScale, ParcelSearchResult
from ..map_sheet_index import find_map_sheet
from .ngii_client import RasterDownloadResult
from .ngii_selectors import NgiiSelectors, load_selectors

DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "ngii_selectors.json"

MAP_SCALE_BUTTON_LABELS = {
    MapScale.SCALE_5000: ":5,000",
    MapScale.SCALE_1000: ":1,000",
}


class NgiiWebClient:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        use_mock: bool | None = None,
        selectors: NgiiSelectors | None = None,
        download_folder_label: str | None = None,
        download_watch_dir: str | None = None,
    ):
        self.username = username or os.environ.get("NGII_USERNAME", "")
        self.password = password or os.environ.get("NGII_PASSWORD", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.username and self.password)
        self.selectors = selectors or load_selectors(DEFAULT_SELECTORS_PATH)
        if download_folder_label:
            self.selectors.download_folder_label = download_folder_label
        if download_watch_dir:
            self.selectors.download_watch_dir = download_watch_dir

    def _login(self, page) -> None:
        page.goto(self.selectors.login_url)
        page.get_by_role("link", name="로그인").click()
        with page.expect_popup() as popup_info:
            page.get_by_role("link", name=self.selectors.id_login_link_name).click()
        popup = popup_info.value
        username_field = popup.get_by_placeholder(self.selectors.username_placeholder)
        if not username_field.is_visible():
            raise RuntimeError("국토정보플랫폼 로그인 폼을 찾을 수 없습니다")
        username_field.fill(self.username)
        popup.get_by_placeholder(self.selectors.password_placeholder).fill(self.password)
        popup.get_by_role("button", name=self.selectors.login_submit_button_name).click()
        popup.close()

    def download_topo(
        self,
        result: ParcelSearchResult,
        coord_system: CoordSystem,
        map_scale: MapScale,
        sheet_features: list[dict],
        output_path: str,
    ) -> RasterDownloadResult:
        if self.use_mock:
            _write_mock_raster_stub(output_path, "TOPO", result, coord_system)
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

        self._log_sheet_no_best_effort(result, map_scale, sheet_features)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            self._login(page)
            self._search_location(page, result.address, map_scale)
            self._select_category_and_items(page)
            known_files = self._snapshot_watch_dir()
            self._submit_transfer(page)
            file_path = self._wait_for_downloaded_file(
                known_files, output_path, timeout_seconds=60.0, poll_interval_seconds=2.0, raise_on_timeout=True
            )
        return RasterDownloadResult(file_path=file_path, coord_system=coord_system)

    def download_ortho(
        self,
        result: ParcelSearchResult,
        coord_system: CoordSystem,
        map_scale: MapScale,
        sheet_features: list[dict],
        output_path: str,
        poll_interval_seconds: float = 15.0,
        timeout_seconds: float = 600.0,
    ) -> RasterDownloadResult | None:
        if self.use_mock:
            _write_mock_raster_stub(output_path, "ORTHO", result, coord_system)
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

        self._log_sheet_no_best_effort(result, map_scale, sheet_features)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            self._login(page)
            self._search_location(page, result.address, map_scale)
            self._select_category_and_items(page)
            known_files = self._snapshot_watch_dir()
            self._submit_transfer(page)
            file_path = self._wait_for_downloaded_file(
                known_files,
                output_path,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                raise_on_timeout=False,
            )
        if file_path is None:
            return None
        return RasterDownloadResult(file_path=file_path, coord_system=coord_system)

    def _log_sheet_no_best_effort(
        self, result: ParcelSearchResult, map_scale: MapScale, sheet_features: list[dict]
    ) -> str | None:
        try:
            sheet_no = find_map_sheet(result.x, result.y, map_scale, sheet_features)
            print(f"도엽 {sheet_no} 부근 다운로드 시도 ({map_scale.value})")
            return sheet_no
        except Exception:
            return None

    def _search_location(self, page, address: str, map_scale: MapScale) -> None:
        page.get_by_role("button", name="국토정보맵").click()
        page.get_by_role("link", name="통합지도검색").click()
        page.locator(self.selectors.search_keyword_selector).fill(address)
        page.locator(self.selectors.search_keyword_selector).press("Enter")
        page.get_by_role("button", name="간편지도 검색").click()
        page.get_by_role("button", name="인덱스").click()
        page.get_by_role("button", name=MAP_SCALE_BUTTON_LABELS[map_scale]).click()
        for _ in range(self.selectors.map_click_count):
            page.locator(self.selectors.map_pin_click_selector).click()

    def _select_category_and_items(self, page) -> None:
        page.get_by_role("button", name="검색").nth(4).click()
        page.get_by_role("button", name="수치지도", exact=False).click()
        page.get_by_role("button", name="수치지형도(DXF파일)", exact=False).click()
        page.locator("li > label > i").first.click()
        page.locator("li > label > i").first.click()
        page.locator("li:nth-child(4) > label > i").first.click()
        page.locator("li:nth-child(6) > label > i").first.click()
        page.get_by_role("button", name="다운로드", exact=True).click()

    def _submit_transfer(self, page) -> None:
        page.locator(".headline > label:nth-child(2) > i").click()
        with page.expect_popup() as popup_info:
            page.locator("#modalPopup").get_by_role("button", name="다운로드").click()
        popup = popup_info.value
        popup.get_by_role("button", name="전체 다운로드").click()
        popup.get_by_text(self.selectors.download_folder_label).click()
        popup.get_by_role("button", name="전송시작").click()
        popup.close()

    def _snapshot_watch_dir(self) -> set:
        watch_dir = Path(self.selectors.download_watch_dir)
        return set(watch_dir.iterdir()) if watch_dir.exists() else set()

    def _wait_for_downloaded_file(
        self,
        known_files: set,
        output_path: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
        raise_on_timeout: bool,
    ) -> str | None:
        watch_dir = Path(self.selectors.download_watch_dir)
        start = time.monotonic()
        last_seen_size: dict[Path, int] = {}
        while True:
            if watch_dir.exists():
                new_files = set(watch_dir.iterdir()) - known_files
                if new_files:
                    newest = max(new_files, key=lambda p: p.stat().st_mtime)
                    current_size = newest.stat().st_size
                    if last_seen_size.get(newest) == current_size:
                        Path(output_path).write_bytes(newest.read_bytes())
                        return output_path
                    last_seen_size[newest] = current_size
            if time.monotonic() - start >= timeout_seconds:
                if raise_on_timeout:
                    raise RuntimeError(f"{watch_dir}에서 다운로드된 파일을 찾지 못했습니다 (타임아웃)")
                return None
            time.sleep(poll_interval_seconds)


def _write_mock_raster_stub(
    output_path: str, kind: str, result: ParcelSearchResult, coord_system: CoordSystem
) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(
            f"{kind} mock raster\n"
            f"pnu={result.pnu}\n"
            f"x={result.x}\n"
            f"y={result.y}\n"
            f"coord_system={coord_system.value}\n"
        )
