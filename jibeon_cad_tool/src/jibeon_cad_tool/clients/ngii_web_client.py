import os
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ..models import CoordSystem, MapScale, ParcelSearchResult
from ..map_sheet_index import find_map_sheet_in_gpkg
from .ngii_client import RasterDownloadResult
from .ngii_selectors import NgiiSelectors, load_selectors

DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "ngii_selectors.json"
DEFAULT_SHEET_INDEX_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

MAP_SCALE_BUTTON_LABELS = {
    MapScale.SCALE_5000: ":5,000",
    MapScale.SCALE_1000: ":1,000",
}

# 카테고리 클릭 후 파일 종류를 한 번 더 선택해야 하는 경우의 라벨.
# 수치지도는 "수치지형도(DXF파일)" 하위 항목을 한 번 더 클릭해야 체크박스가 나타나지만,
# 정사영상은 카테고리 클릭만으로 바로 체크박스 목록이 나오는 것으로 보여 item_label이 없다
# (정사영상 경로는 실 계정으로 아직 끝까지 검증되지 않음 — 실패하면 알려달라고 안내 필요).
TOPO_CATEGORY_LABEL = "수치지도"
TOPO_ITEM_LABEL = "수치지형도(DXF파일)"
ORTHO_CATEGORY_LABEL = "정사영상"
ORTHO_ITEM_LABEL = None

# 사용자가 팝업 창에서 직접 로그인을 완료할 때까지 기다리는 최대 시간.
# 자동 아이디/비밀번호 입력은 봇 탐지로 조용히 차단되는 것이 확인되어, 로그인은
# 사용자가 직접 하고 그 이후(검색·다운로드)만 자동화하는 방식으로 전환했다.
LOGIN_WAIT_TIMEOUT_MS = 300000


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
        # 자동 아이디/비밀번호 입력은 국토정보플랫폼의 봇 탐지에 조용히 차단되는 것이
        # 확인되어, 로그인 창을 열어주고 사용자가 직접 로그인을 완료할 때까지 기다린다.
        page.goto(self.selectors.login_url)
        page.get_by_role("link", name="로그인").click()
        with page.expect_popup() as popup_info:
            page.get_by_role("link", name=self.selectors.id_login_link_name).click()
        popup = popup_info.value
        try:
            popup.wait_for_event("close", timeout=LOGIN_WAIT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            raise RuntimeError(
                "로그인 대기 시간이 초과되었습니다 — 브라우저 창에서 로그인을 완료한 뒤 다시 시도해 주세요"
            ) from None

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

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            self._login(page)
            self._search_location(page, result, map_scale, sheet_features)
            self._select_category_and_items(page, TOPO_CATEGORY_LABEL, TOPO_ITEM_LABEL)
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

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            self._login(page)
            self._search_location(page, result, map_scale, sheet_features)
            self._select_category_and_items(page, ORTHO_CATEGORY_LABEL, ORTHO_ITEM_LABEL)
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

    def _search_location(
        self, page, result: ParcelSearchResult, map_scale: MapScale, sheet_features: list[dict]
    ) -> str:
        # 도엽번호로 직접 검색하는 방식 — 지도를 클릭해 위치를 고르는 방식은 검색 세션마다
        # 화면 배치가 달라져 자동화할 수 없음이 확인되어, 좌표 → 도엽번호(map_sheet_index) →
        # 도엽번호 텍스트 검색 → 검색 결과 목록에서 정확히 일치하는 항목 클릭으로 대체했다.
        # 도엽번호는 국토지리정보원이 공식 배포하는 전국 GeoPackage 인덱스(data/*.gpkg)에서
        # 직접 조회한다 — 찾지 못하면(좌표가 인덱스에 없음) 여기서 바로 ValueError가 올라간다.
        # sheet_features 매개변수는 이전 설계(로컬 GeoJSON fixture)의 흔적으로 이제 쓰이지
        # 않는다 — pipeline.py의 공개 시그니처를 바꾸지 않기 위해 남겨두었다.
        sheet_no = find_map_sheet_in_gpkg(result.x, result.y, map_scale, DEFAULT_SHEET_INDEX_DIR)

        # "국토정보맵" 버튼은 페이지에 2개 있음(상단 메뉴 트리거 / 홈 화면 바로가기 카드) —
        # 상단 메뉴("메인 메뉴") 쪽으로 정확히 지정해야 드롭다운이 열려 "통합지도검색" 링크가 나타남
        page.get_by_label("메인 메뉴").get_by_role("button", name="국토정보맵").click()
        page.get_by_role("link", name="통합지도검색").click()
        page.get_by_role("button", name="간편지도 검색").click()
        page.get_by_role("button", name="인덱스").click()
        # 축척 버튼도 페이지에 2개 있어 "#totalSearch" 영역으로 범위를 좁혀야 정확한 버튼을 클릭함
        page.locator("#totalSearch").get_by_role("button", name=MAP_SCALE_BUTTON_LABELS[map_scale]).click()
        page.locator(self.selectors.search_keyword_selector).fill(sheet_no)
        page.locator(self.selectors.search_keyword_selector).press("Enter")
        page.get_by_text(sheet_no, exact=True).first.click()
        return sheet_no

    def _select_category_and_items(self, page, category_label: str, item_label: str | None) -> None:
        page.get_by_role("button", name=category_label, exact=False).click()
        if item_label:
            page.get_by_text(item_label, exact=False).first.click()
        page.get_by_role("checkbox").click()

    def _submit_transfer(self, page) -> None:
        with page.expect_popup() as popup_info:
            page.get_by_role("button", name="다운로드", exact=True).click()
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
