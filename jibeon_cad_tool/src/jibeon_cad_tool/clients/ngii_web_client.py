import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..models import CoordSystem, MapScale, ParcelSearchResult
from ..map_sheet_index import find_map_sheet
from .ngii_client import RasterDownloadResult
from .ngii_selectors import NgiiSelectors, load_selectors

DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "ngii_selectors.json"


class NgiiWebClient:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        use_mock: bool | None = None,
        selectors: NgiiSelectors | None = None,
    ):
        self.username = username or os.environ.get("NGII_USERNAME", "")
        self.password = password or os.environ.get("NGII_PASSWORD", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.username and self.password)
        self.selectors = selectors or load_selectors(DEFAULT_SELECTORS_PATH)

    def _login(self, page) -> None:
        page.goto(self.selectors.login_url)
        page.click(self.selectors.login_trigger_selector)
        if not page.locator(self.selectors.username_selector).is_visible():
            raise RuntimeError("국토정보플랫폼 로그인 폼을 찾을 수 없습니다")
        page.fill(self.selectors.username_selector, self.username)
        page.fill(self.selectors.password_selector, self.password)
        page.click(self.selectors.login_submit_selector)

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

        sheet_no = find_map_sheet(result.x, result.y, map_scale, sheet_features)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            self._login(page)
            self._request_sheet(page, sheet_no, map_scale)
            file_path = self._download_ready_file(page, output_path)
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

        sheet_no = find_map_sheet(result.x, result.y, map_scale, sheet_features)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            self._login(page)
            self._request_sheet(page, sheet_no, map_scale)

            start = time.monotonic()
            while True:
                if page.locator(self.selectors.download_link_selector).is_visible():
                    file_path = self._download_ready_file(page, output_path)
                    return RasterDownloadResult(file_path=file_path, coord_system=coord_system)
                if time.monotonic() - start >= timeout_seconds:
                    return None
                time.sleep(poll_interval_seconds)

    def _request_sheet(self, page, sheet_no: str, map_scale: MapScale) -> None:
        page.goto(self.selectors.catalog_url)
        page.fill(self.selectors.scale_select_selector, map_scale.value)
        page.fill(self.selectors.sheet_no_input_selector, sheet_no)
        page.click(self.selectors.search_button_selector)
        page.click(self.selectors.cart_add_selector)
        page.click(self.selectors.request_submit_selector)

    def _download_ready_file(self, page, output_path: str) -> str:
        with page.expect_download() as download_info:
            page.click(self.selectors.download_link_selector)
        download = download_info.value
        downloaded_path = download.path()
        Path(output_path).write_bytes(Path(downloaded_path).read_bytes())
        return output_path


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
