# NGII 실제 흐름 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `NgiiWebClient`가 국토정보플랫폼의 실제 웹 흐름(도엽번호 텍스트 검색이 아니라, 주소 검색 → 지도 클릭 → 카테고리/체크박스 선택 → 전송관리 팝업 다운로드)을 자동화하도록 재구현한다. 이 계획은 `docs/superpowers/plans/2026-08-30-jibeon-cad-real-api-integration.md`의 Task 6~8에서 만든 `NgiiSelectors`/`NgiiWebClient`를 대체한다.

**Architecture:** `NgiiSelectors`를 이전의 고정 필드(로그인 폼, 도엽 검색 폼 등)에서 실제 흐름에 맞는 새 필드 집합으로 교체하고, `NgiiWebClient`의 내부 메서드를 캡처된 실제 클릭·입력 순서에 맞춰 다시 작성한다. 범용 JSON 인터프리터(DSL)는 만들지 않고, 캡처된 흐름을 Python 코드로 직접 반영하며, 사용자 환경에 따라 달라지는 값(저장 폴더, 감시 디렉터리)만 설정 파일로 분리한다. `pipeline.py`와 UI는 변경하지 않는다 — `NgiiWebClient`의 공개 시그니처(`download_topo`/`download_ortho`)는 그대로 유지된다.

**Tech Stack:** Python 3.11+, playwright(sync API), shapely, pytest, unittest.mock

## Global Constraints

- `NgiiWebClient.download_topo`/`download_ortho`의 공개 시그니처(`result, coord_system, map_scale, sheet_features, output_path`, ortho는 추가로 `poll_interval_seconds`/`timeout_seconds`)는 변경하지 않는다 — `pipeline.py`는 이 플랜에서 수정하지 않는다.
- `map_sheet_index.py`(좌표→도엽번호)는 삭제하지 않고 로그·디버깅 참고용으로만 호출한다 — 실패해도 다운로드 흐름을 막지 않는다(best-effort).
- 로그인 실패 시 즉시 예외, 재시도 없음(계정 잠금 방지) — 기존 정책 유지.
- 수치지형도(`download_topo`)는 다운로드가 확인되지 않으면 예외를 던진다(동기, 승인 대기 없음이 전제). 정사영상(`download_ortho`)은 타임아웃 시 예외 대신 `None`을 반환한다(전체 파이프라인을 실패시키지 않음) — 기존 정책 유지.
- `map_pin_click_selector`(`.ol-unselectable > div:nth-child(3)`)와 카테고리/체크박스 클릭 순서는 이번에 캡처된 세션 그대로 코드에 반영하며, 다른 지번/축척 조합에서 깨질 수 있다는 위험을 사용자가 인지하고 승인했다 — 더 견고하게 만드는 것은 이 플랜의 범위 밖이다.
- `download_folder_label`/`download_watch_dir`는 사용자 로컬 환경에 따라 달라지므로 `config/ngii_selectors.json`에 플레이스홀더로 남긴다.

---

## 파일 구조 (기존 구조에서 변경되는 부분)

```
jibeon_cad_tool/
├── config/
│   └── ngii_selectors.json                   # 수정: 새 스키마로 전면 교체
├── src/jibeon_cad_tool/
│   └── clients/
│       ├── ngii_selectors.py                 # 수정: NgiiSelectors 필드 전면 교체
│       └── ngii_web_client.py                # 수정: _login 재작성, 새 메서드 추가, 옛 메서드 제거
└── tests/
    ├── test_ngii_selectors.py                # 수정: 새 필드에 맞춰 테스트 교체
    └── test_ngii_web_client.py                # 수정: 새 흐름에 맞춰 테스트 교체
```

---

### Task 1: `NgiiSelectors` 새 스키마 + `config/ngii_selectors.json` 교체

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_selectors.py`
- Modify: `jibeon_cad_tool/config/ngii_selectors.json`
- Modify: `jibeon_cad_tool/tests/test_ngii_selectors.py`

**Interfaces:**
- Produces: `NgiiSelectors` 데이터클래스 — 필드: `login_url: str`, `id_login_link_name: str`, `username_placeholder: str`, `password_placeholder: str`, `login_submit_button_name: str`, `search_keyword_selector: str`, `map_pin_click_selector: str`, `map_click_count: int`, `download_folder_label: str`, `download_watch_dir: str`
- `load_selectors(path: Path) -> NgiiSelectors` 함수 시그니처는 그대로 유지

- [ ] **Step 1: 실패하는 테스트로 교체**

`jibeon_cad_tool/tests/test_ngii_selectors.py`의 전체 내용을 다음으로 교체:

```python
# tests/test_ngii_selectors.py
from pathlib import Path

from jibeon_cad_tool.clients.ngii_selectors import load_selectors

CONFIG_PATH = Path(__file__).parent.parent / "config" / "ngii_selectors.json"


def test_load_selectors_reads_all_fields_from_json():
    selectors = load_selectors(CONFIG_PATH)

    assert selectors.login_url == "https://map.ngii.go.kr"
    assert selectors.id_login_link_name
    assert selectors.username_placeholder
    assert selectors.password_placeholder
    assert selectors.login_submit_button_name
    assert selectors.search_keyword_selector == "#totalSearchKeyword"
    assert selectors.map_pin_click_selector
    assert selectors.map_click_count == 2
    assert selectors.download_folder_label
    assert selectors.download_watch_dir


def test_load_selectors_from_custom_path(tmp_path):
    custom_config = tmp_path / "custom_selectors.json"
    custom_config.write_text(
        '{"login_url": "https://example.com", "id_login_link_name": "a",'
        ' "username_placeholder": "b", "password_placeholder": "c",'
        ' "login_submit_button_name": "d", "search_keyword_selector": "#kw",'
        ' "map_pin_click_selector": ".pin", "map_click_count": 2,'
        ' "download_folder_label": "e", "download_watch_dir": "f"}',
        encoding="utf-8",
    )

    selectors = load_selectors(custom_config)

    assert selectors.login_url == "https://example.com"
    assert selectors.map_click_count == 2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_selectors.py -v`
Expected: FAIL — `NgiiSelectors(**data)`가 옛 필드 이름(`login_trigger_selector` 등)을 기대하는 `config/ngii_selectors.json`의 새 필드들과 맞지 않아 `TypeError`

- [ ] **Step 3: `ngii_selectors.py` 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_selectors.py`의 `NgiiSelectors` 데이터클래스 정의를 다음으로 교체 (`load_selectors` 함수는 그대로 둔다):

```python
@dataclass
class NgiiSelectors:
    login_url: str
    id_login_link_name: str
    username_placeholder: str
    password_placeholder: str
    login_submit_button_name: str
    search_keyword_selector: str
    map_pin_click_selector: str
    map_click_count: int
    download_folder_label: str
    download_watch_dir: str
```

- [ ] **Step 4: `config/ngii_selectors.json` 새 스키마로 교체**

`jibeon_cad_tool/config/ngii_selectors.json`의 전체 내용을 다음으로 교체 (실제 캡처된 값 사용, 저장 폴더/감시 디렉터리는 사용자 환경별로 다르므로 플레이스홀더 유지):

```json
{
  "login_url": "https://map.ngii.go.kr",
  "id_login_link_name": "아이디 로그인 국토정보플랫폼 회원가입시 등록한 아이디와 비밀번호를 이용하여 로그인하는 서비스입니다",
  "username_placeholder": "아이디 (영문, 숫자, 혼합 6~12자리)",
  "password_placeholder": "비밀번호 (영문, 숫자, 특수문자 10자~15자)",
  "login_submit_button_name": "회원 들어가기",
  "search_keyword_selector": "#totalSearchKeyword",
  "map_pin_click_selector": ".ol-unselectable > div:nth-child(3)",
  "map_click_count": 2,
  "download_folder_label": "PLACEHOLDER_전송관리에서_클릭할_저장_폴더_텍스트_사용자_환경에_맞게_설정",
  "download_watch_dir": "PLACEHOLDER_실제_파일이_저장되는_로컬_경로_사용자_환경에_맞게_설정"
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_selectors.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: `ngii_web_client.py`/`test_ngii_web_client.py`가 옛 필드를 참조해 깨지는지 확인 (다음 태스크에서 수정 예정이므로 지금은 실패해도 됨)**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: FAIL (Task 2/3에서 `ngii_web_client.py`와 그 테스트를 새 필드에 맞춰 재작성하기 전까지는 실패가 정상 — 지금 단계에서 고치지 않는다)

- [ ] **Step 7: Commit**

```bash
cd jibeon_cad_tool
git add config/ngii_selectors.json src/jibeon_cad_tool/clients/ngii_selectors.py tests/test_ngii_selectors.py
git commit -m "feat: replace NgiiSelectors with fields matching the real captured NGII flow"
```

---

### Task 2: `_login` 재작성 (팝업 기반)

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`
- Modify: `jibeon_cad_tool/tests/test_ngii_web_client.py`

**Interfaces:**
- Consumes: 새 `NgiiSelectors` (Task 1)
- Produces: `NgiiWebClient._login(page) -> None` — 실제 캡처된 흐름(홈 → "로그인" 링크 → "아이디 로그인" 링크 클릭 시 팝업 오픈 → 팝업 안에서 아이디/비밀번호 입력 → "회원 들어가기" 클릭 → 팝업 닫기)을 반영. 로그인 폼이 뜨지 않으면 `RuntimeError`, 재시도 없음

이 태스크는 `__init__`(이미 존재, 변경 없음)과 `_login`만 재작성한다. `download_topo`/`download_ortho`와 다른 메서드들은 Task 3에서 다룬다 — 지금은 손대지 않는다(테스트도 마찬가지로, 이번 태스크는 로그인 관련 테스트 4개만 새로 작성한다).

- [ ] **Step 1: 기존 `tests/test_ngii_web_client.py`의 로그인 관련 부분을 새 흐름에 맞춰 교체**

`jibeon_cad_tool/tests/test_ngii_web_client.py` 파일 맨 위, `make_selectors()` 헬퍼 함수를 다음으로 교체 (이 함수를 참조하는 다른 기존 테스트들이 있다면, Task 3에서 함께 정리되므로 지금은 이 함수 정의만 바꾼다):

```python
from unittest.mock import MagicMock

import pytest

from jibeon_cad_tool.clients.ngii_selectors import NgiiSelectors
from jibeon_cad_tool.clients.ngii_web_client import NgiiWebClient


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
```

같은 파일에서 로그인 관련 테스트 함수 4개(`test_defaults_to_mock_when_no_credentials`, `test_does_not_default_to_mock_when_credentials_present`, `test_login_fills_credentials_and_clicks_submit`, `test_login_raises_when_login_form_never_becomes_visible`)를 다음으로 교체:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v -k login`
Expected: FAIL — `_login`이 아직 옛 흐름(팝업 없이 같은 페이지에서 처리)으로 구현되어 있어 `page.expect_popup`을 호출하지 않으므로 새 테스트들이 실패

- [ ] **Step 3: `_login` 재작성**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`에서 기존 `_login` 메서드를 다음으로 교체:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v -k login`
Expected: PASS (4 passed) — 나머지(다운로드 관련) 테스트들은 여전히 실패해도 정상, Task 3에서 다룬다

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/ngii_web_client.py tests/test_ngii_web_client.py
git commit -m "feat: rewrite NgiiWebClient login flow to match popup-based real site behavior"
```

---

### Task 3: 위치 검색·자료 선택·다운로드 흐름 재작성

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`
- Modify: `jibeon_cad_tool/tests/test_ngii_web_client.py`

**Interfaces:**
- Consumes: `MapScale`, `ParcelSearchResult`, `CoordSystem` from `jibeon_cad_tool.models`; `find_map_sheet` from `jibeon_cad_tool.map_sheet_index` (best-effort 로깅용으로만); `RasterDownloadResult` from `jibeon_cad_tool.clients.ngii_client`
- Produces (공개 시그니처는 기존과 동일하게 유지):
  - `NgiiWebClient.download_topo(result, coord_system, map_scale, sheet_features, output_path) -> RasterDownloadResult`
  - `NgiiWebClient.download_ortho(result, coord_system, map_scale, sheet_features, output_path, poll_interval_seconds=15.0, timeout_seconds=600.0) -> RasterDownloadResult | None`
- 새 비공개 메서드: `_search_location(page, address, map_scale)`, `_select_category_and_items(page)`, `_submit_transfer(page)`, `_wait_for_downloaded_file(output_path, timeout_seconds, poll_interval_seconds, raise_on_timeout) -> str | None`
- 제거되는 메서드: `_request_sheet`, `_download_ready_file` (이번 태스크에서 완전히 대체됨)

이 태스크가 완료되면 `ngii_web_client.py`는 옛 카탈로그 검색 방식(도엽번호 텍스트 입력)을 전혀 사용하지 않는다.

- [ ] **Step 1: 실패하는 테스트로 교체**

`jibeon_cad_tool/tests/test_ngii_web_client.py`에서 Task 1 이전에 있던 다운로드 관련 테스트들(`test_download_topo_mock_mode_writes_stub`, `test_download_topo_real_mode_logs_in_searches_and_downloads`, `test_download_ortho_real_mode_polls_until_ready`, `test_download_ortho_real_mode_returns_none_on_timeout`)과 그 위의 `SAMPLE_FEATURES`/`make_search_result`/`_FakePlaywrightCM` 정의를 모두 다음으로 교체 (파일의 로그인 관련 부분은 Task 2에서 이미 완료했으므로 그대로 둔다):

```python
from pathlib import Path

from jibeon_cad_tool.models import CoordSystem, MapScale, ParcelSearchResult


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
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    output_path = str(tmp_path / "out.tif")
    selectors = make_selectors()
    selectors.download_watch_dir = str(watch_dir)

    client = NgiiWebClient(username="u", password="p", use_mock=False, selectors=selectors)
    page = MagicMock()
    popup = MagicMock()
    popup.get_by_placeholder.return_value.is_visible.return_value = True
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
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path
    )

    assert result is not None
    assert Path(output_path).read_bytes() == b"dummy-tif-bytes"
    page.locator.assert_any_call("#totalSearchKeyword")


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
    popup.get_by_placeholder.return_value.is_visible.return_value = True
    page.expect_popup.return_value.__enter__.return_value.value = popup
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
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path,
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
    popup.get_by_placeholder.return_value.is_visible.return_value = True
    page.expect_popup.return_value.__enter__.return_value.value = popup
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
        make_search_result(), CoordSystem.GRS80_MID, MapScale.SCALE_5000, SAMPLE_FEATURES, output_path,
        poll_interval_seconds=0.01, timeout_seconds=1.0,
    )

    assert result is None


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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: FAIL — `download_topo`/`download_ortho`가 아직 옛 `_request_sheet`/`_download_ready_file`(도엽번호 텍스트 검색 방식)을 호출하므로, 새 테스트가 기대하는 `page.locator("#totalSearchKeyword")` 호출이나 `download_watch_dir` 폴링이 일어나지 않아 실패

- [ ] **Step 3: `ngii_web_client.py`에 새 메서드 추가, 옛 메서드 제거**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py` 상단 import를 다음과 같이 정리 (기존 `from ..map_sheet_index import find_map_sheet`는 유지, `Path` import도 이미 있으므로 유지):

```python
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
```

`download_topo`/`download_ortho` 메서드를 다음으로 교체 (mock 분기는 완전히 동일하게 유지):

```python
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
            self._submit_transfer(page)
            file_path = self._wait_for_downloaded_file(
                output_path, timeout_seconds=60.0, poll_interval_seconds=2.0, raise_on_timeout=True
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
            self._submit_transfer(page)
            file_path = self._wait_for_downloaded_file(
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
    ) -> None:
        try:
            find_map_sheet(result.x, result.y, map_scale, sheet_features)
        except ValueError:
            pass

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

    def _wait_for_downloaded_file(
        self,
        output_path: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
        raise_on_timeout: bool,
    ) -> str | None:
        watch_dir = Path(self.selectors.download_watch_dir)
        known_files = set(watch_dir.iterdir()) if watch_dir.exists() else set()
        start = time.monotonic()
        while True:
            if watch_dir.exists():
                new_files = set(watch_dir.iterdir()) - known_files
                if new_files:
                    newest = max(new_files, key=lambda p: p.stat().st_mtime)
                    Path(output_path).write_bytes(newest.read_bytes())
                    return output_path
            if time.monotonic() - start >= timeout_seconds:
                if raise_on_timeout:
                    raise RuntimeError(f"{watch_dir}에서 다운로드된 파일을 찾지 못했습니다 (타임아웃)")
                return None
            time.sleep(poll_interval_seconds)
```

`_request_sheet`와 `_download_ready_file` 메서드는 완전히 삭제한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: PASS (전체 — 로그인 4개 + 다운로드 4개 = 8개)

- [ ] **Step 5: 전체 스위트 회귀 확인**

Run: `cd jibeon_cad_tool && pytest -v`
Expected: 전체 PASS. `test_pipeline.py`는 `NgiiWebClient(use_mock=True)`만 사용하므로 이 태스크의 real-mode 변경과 무관하게 그대로 통과해야 한다.

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/ngii_web_client.py tests/test_ngii_web_client.py
git commit -m "feat: rewrite NgiiWebClient download flow to match real address-search + map-click + transfer-popup flow"
```

---

## 후속 작업 (이 플랜 범위 밖)

- `config/ngii_selectors.json`의 `download_folder_label`/`download_watch_dir`는 사용자가 실행 환경(로컬에 마운트된 구글드라이브 경로 등)에 맞게 채워야 한다
- `_select_category_and_items`의 클릭 순서는 이번 한 번의 캡처(광주 지역 주소, 수치지형도 DXF)에서만 검증됨 — 다른 지역/축척/자료 종류 조합에서 실패할 경우 더 견고한 방식(텍스트 기반 동적 탐색 등)으로 재설계 필요
- `map_pin_click_selector`가 다른 지번에서 항상 유효한 핀 위치를 가리키는지는 실사용 중 추가 검증 필요
- 로그인 위젯이 이번 캡처와 다른 인증 방식(모바일 신분증, 간편인증 등)으로 전환되는 경우는 다루지 않음
