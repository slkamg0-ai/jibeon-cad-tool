# 실 API 연동 (브이월드/국토정보플랫폼) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `jibeon_cad_tool`의 목업 전용 `VWorldClient`/`NgiiClient`를 실제 브이월드 Open API(검색+Data API) 호출과, 국토정보플랫폼 로그인 세션 기반 Playwright 웹 자동화(`NgiiWebClient`)로 교체한다. 좌표→도엽번호 변환을 위한 로컬 도엽 인덱스 조회 기능과 `.env` 기반 자격증명 관리를 함께 추가한다.

**Architecture:** 기존 모듈 경계(`models.py`/`geometry.py`/`dxf_export.py`/`pipeline.py`/`clients/`/`ui/`)를 그대로 유지한 채, `clients/vworld_client.py`의 real-mode 메서드를 채우고, `clients/ngii_client.py`를 대체하는 `clients/ngii_web_client.py`(Playwright 기반)를 새로 추가한다. NGII 사이트의 취약한 UI 셀렉터는 코드에 하드코딩하지 않고 `config/ngii_selectors.json`(사용자가 직접 캡처해 채우는 설정 파일)으로 분리한다. 좌표→도엽번호 변환은 새 `map_sheet_index.py`가 로컬 GeoJSON 인덱스 자산을 공간 조회한다.

**Tech Stack:** Python 3.11+, python-dotenv, playwright(sync API), requests, requests-mock(테스트), shapely, ezdxf, pyproj, pytest

## Global Constraints

- `.env`(`VWORLD_API_KEY`, `NGII_API_KEY`, `NGII_USERNAME`, `NGII_PASSWORD`)는 `.gitignore`에 등록되어 커밋되지 않는다.
- 브이월드 검색 요청은 `crs=EPSG:5186`을 명시적으로 포함해, 응답 좌표가 항상 `CoordSystem.GRS80_MID` 기준이 되도록 한다.
- 브이월드 지적도는 CAD 원본이 아니라 Data API(WFS GetFeature, `LP_PA_CBND_BUBUN` 레이어)의 GeoJSON으로 받아 기존 `tuple[list[Polygon], int]` 반환 형식을 그대로 유지한다.
- 국토정보플랫폼은 API 키가 아니라 로그인 세션 기반 Playwright 자동화로 동작한다. `NGII_API_KEY`는 이번 범위에서 사용하지 않는다.
- NGII 로그인 실패 시 즉시 예외를 던지고 재시도하지 않는다(계정 잠금 방지).
- 정사영상 신청은 승인 대기가 있을 수 있으므로 짧은 간격으로 폴링하다가 10분 타임아웃을 넘으면 파이프라인을 실패시키지 않고 "신청 완료·다운로드 대기" 상태로 처리한다(수치지형도는 신청 직후 다운로드 시도).
- 축척은 `MapScale.SCALE_5000`(1:5,000)이 기본값이고 `MapScale.SCALE_1000`(1:1,000)을 선택할 수 있어야 한다.
- NGII UI 셀렉터는 코드에 하드코딩하지 않고 `config/ngii_selectors.json`에서 로드한다 — 이 설정 파일의 실제 값은 사용자가 `playwright codegen`으로 직접 캡처해야 하며, 이번 플랜은 그 값을 채우는 작업을 포함하지 않는다(설계 문서의 미해결 항목).

---

## 파일 구조 (기존 구조에 추가되는 부분)

```
jibeon_cad_tool/
├── .env.example                              # 신규
├── .gitignore                                # 신규 (.env 제외)
├── config/
│   └── ngii_selectors.json                   # 신규 (사용자 캡처 대상, 기본 placeholder)
├── data/
│   └── map_sheet_index_fixture.geojson       # 신규 (테스트용 샘플 — 실 인덱스는 후속 작업)
├── requirements.txt                          # 수정: python-dotenv, playwright, requests-mock 추가
├── src/jibeon_cad_tool/
│   ├── env.py                                # 신규: .env 로드 래퍼
│   ├── models.py                             # 수정: MapScale enum, ExportOptions.map_scale
│   ├── map_sheet_index.py                    # 신규: 좌표 → 도엽번호 공간 조회
│   ├── clients/
│   │   ├── vworld_client.py                  # 수정: real-mode search/download_cadastral 구현
│   │   ├── ngii_selectors.py                 # 신규: 셀렉터 설정 로더
│   │   └── ngii_web_client.py                # 신규: Playwright 기반 NgiiWebClient
│   ├── pipeline.py                           # 수정: 도엽번호 조회 + NgiiWebClient 연동
│   └── ui/main_window.py                     # 수정: 축척 선택 드롭다운 추가
└── tests/
    ├── test_env.py                           # 신규
    ├── test_map_sheet_index.py               # 신규
    ├── test_ngii_selectors.py                # 신규
    ├── test_ngii_web_client.py               # 신규
    ├── test_vworld_client.py                 # 수정: real-mode 테스트 추가
    ├── test_pipeline.py                      # 수정
    └── test_ui_main_window.py                # 수정
```

---

### Task 1: 자격증명 로딩 (`env.py`) + 의존성/`.env.example`/`.gitignore`

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/env.py`
- Create: `jibeon_cad_tool/.env.example`
- Create: `jibeon_cad_tool/.gitignore`
- Modify: `jibeon_cad_tool/requirements.txt`
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/ui/app.py`
- Test: `jibeon_cad_tool/tests/test_env.py`

**Interfaces:**
- Produces: `load_env(dotenv_path: Path | None = None) -> None` — `python-dotenv`의 `load_dotenv`를 감싸 `os.environ`에 값을 채움 (이미 설정된 환경변수는 덮어쓰지 않음: `override=False`)
- `ui/app.py`의 `build_application`은 호출 시작 시 `load_env()`를 호출

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_env.py
import os

from jibeon_cad_tool.env import load_env


def test_load_env_sets_environment_variable_from_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_JIBEON_VAR=hello\n", encoding="utf-8")
    monkeypatch.delenv("TEST_JIBEON_VAR", raising=False)

    load_env(dotenv_path=env_file)

    assert os.environ["TEST_JIBEON_VAR"] == "hello"
    del os.environ["TEST_JIBEON_VAR"]


def test_load_env_does_not_override_existing_environment_variable(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_JIBEON_VAR=from_file\n", encoding="utf-8")
    monkeypatch.setenv("TEST_JIBEON_VAR", "from_shell")

    load_env(dotenv_path=env_file)

    assert os.environ["TEST_JIBEON_VAR"] == "from_shell"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_env.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.env'` (python-dotenv도 아직 미설치이므로 requirements.txt 수정과 설치를 먼저 진행한 뒤 이 실패를 관찰한다)

- [ ] **Step 3: requirements.txt에 의존성 추가**

`jibeon_cad_tool/requirements.txt`에 다음 세 줄을 기존 내용 뒤에 추가:

```text
python-dotenv>=1.0.0
playwright>=1.44.0
requests-mock>=1.11.0
```

Run: `cd jibeon_cad_tool && pip install -r requirements.txt`
Expected: 설치 완료, 에러 없음

- [ ] **Step 4: env.py 구현**

```python
# src/jibeon_cad_tool/env.py
from pathlib import Path

from dotenv import load_dotenv


def load_env(dotenv_path: Path | None = None) -> None:
    load_dotenv(dotenv_path=dotenv_path, override=False)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_env.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: `.env.example` 작성**

```text
# jibeon_cad_tool/.env.example
# 실제 값을 채운 뒤 이 파일을 .env로 복사해서 사용하세요. .env는 git에 커밋되지 않습니다.
VWORLD_API_KEY=
NGII_API_KEY=
NGII_USERNAME=
NGII_PASSWORD=
```

- [ ] **Step 7: `.gitignore` 작성**

```text
# jibeon_cad_tool/.gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 8: `ui/app.py`에 `load_env()` 호출 추가**

`jibeon_cad_tool/src/jibeon_cad_tool/ui/app.py`의 기존 내용:

```python
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def build_application(show: bool = True) -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    if show:
        window.show()
    return app, window


def main() -> int:
    app, _window = build_application(show=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

다음과 같이 수정 (`load_env()` 호출을 `build_application` 최상단에 추가):

```python
import sys

from PySide6.QtWidgets import QApplication

from ..env import load_env
from .main_window import MainWindow


def build_application(show: bool = True) -> tuple[QApplication, MainWindow]:
    load_env()
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    if show:
        window.show()
    return app, window


def main() -> int:
    app, _window = build_application(show=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 9: 기존 앱 엔트리포인트 테스트가 여전히 통과하는지 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_app_entrypoint.py -v`
Expected: PASS (1 passed) — `load_env()`가 `.env` 파일이 없어도 조용히 통과해야 하므로 (`load_dotenv`는 파일이 없으면 아무 것도 하지 않고 `False`를 반환할 뿐 예외를 던지지 않음) 기존 테스트가 그대로 통과해야 한다

- [ ] **Step 10: Commit**

```bash
cd jibeon_cad_tool
git add requirements.txt .env.example .gitignore src/jibeon_cad_tool/env.py src/jibeon_cad_tool/ui/app.py tests/test_env.py
git commit -m "feat: add .env credential loading and playwright/dotenv dependencies"
```

---

### Task 2: `MapScale` enum + `ExportOptions.map_scale`

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/models.py`
- Modify: `jibeon_cad_tool/tests/test_models.py`

**Interfaces:**
- Produces: `MapScale(Enum)` — `SCALE_5000 = "1:5000"`, `SCALE_1000 = "1:1000"`
- `ExportOptions`에 `map_scale: MapScale = MapScale.SCALE_5000` 필드 추가 (기존 필드 뒤에 추가, 기존 필드 순서/기본값은 변경하지 않음)

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_models.py`에 추가)**

`jibeon_cad_tool/tests/test_models.py` 맨 아래에 다음 테스트를 추가:

```python
def test_map_scale_values():
    assert MapScale.SCALE_5000.value == "1:5000"
    assert MapScale.SCALE_1000.value == "1:1000"


def test_export_options_default_map_scale():
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    assert options.map_scale == MapScale.SCALE_5000
```

파일 상단의 import 문을 다음과 같이 수정:

```python
from jibeon_cad_tool.models import (
    BorderShape,
    CoordSystem,
    ExportOptions,
    MapScale,
    ParcelSearchResult,
)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'MapScale' from 'jibeon_cad_tool.models'`

- [ ] **Step 3: models.py 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/models.py`에서 `BorderShape` 클래스 뒤, `ParcelSearchResult` 앞에 다음을 추가:

```python
class MapScale(Enum):
    SCALE_5000 = "1:5000"
    SCALE_1000 = "1:1000"
```

`ExportOptions` 데이터클래스를 다음과 같이 수정 (마지막 필드로 `map_scale` 추가):

```python
@dataclass
class ExportOptions:
    coord_system: CoordSystem
    buffer_meters: float = 100.0
    border_shape: BorderShape = BorderShape.RECTANGLE
    include_topo: bool = False
    include_ortho: bool = False
    map_scale: MapScale = MapScale.SCALE_5000
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_models.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 전체 스위트에 회귀가 없는지 확인**

Run: `cd jibeon_cad_tool && pytest -v`
Expected: 기존 테스트 전부 PASS (신규 필드가 기본값을 가지므로 `ExportOptions(...)`를 호출하는 기존 코드/테스트는 수정 없이 통과해야 함)

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/models.py tests/test_models.py
git commit -m "feat: add MapScale enum and ExportOptions.map_scale field"
```

---

### Task 3: 도엽 인덱스 공간 조회 (`map_sheet_index.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/map_sheet_index.py`
- Create: `jibeon_cad_tool/tests/fixtures/map_sheet_index_fixture.geojson`
- Test: `jibeon_cad_tool/tests/test_map_sheet_index.py`

**Interfaces:**
- Consumes: `MapScale` from `jibeon_cad_tool.models`
- Produces:
  - `load_index(path: Path) -> list[dict]` — GeoJSON `FeatureCollection`의 `features` 리스트를 반환
  - `find_map_sheet(x: float, y: float, scale: MapScale, features: list[dict]) -> str` — 좌표를 포함하는 도엽의 `sheet_no` 속성값을 반환. 포함하는 도엽이 없으면 `ValueError`

- [ ] **Step 1: 테스트용 fixture GeoJSON 작성**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"scale": "1:5000", "sheet_no": "358051"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[198000.0, 453000.0], [199000.0, 453000.0], [199000.0, 454000.0], [198000.0, 454000.0], [198000.0, 453000.0]]]
      }
    },
    {
      "type": "Feature",
      "properties": {"scale": "1:1000", "sheet_no": "35805025"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[198000.0, 453000.0], [198500.0, 453000.0], [198500.0, 453500.0], [198000.0, 453500.0], [198000.0, 453000.0]]]
      }
    }
  ]
}
```

파일 경로: `jibeon_cad_tool/tests/fixtures/map_sheet_index_fixture.geojson`

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_map_sheet_index.py
from pathlib import Path

import pytest

from jibeon_cad_tool.models import MapScale
from jibeon_cad_tool.map_sheet_index import find_map_sheet, load_index

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "map_sheet_index_fixture.geojson"


def test_load_index_returns_features_list():
    features = load_index(FIXTURE_PATH)
    assert len(features) == 2
    assert features[0]["properties"]["sheet_no"] == "358051"


def test_find_map_sheet_returns_sheet_no_for_contained_point():
    features = load_index(FIXTURE_PATH)
    sheet_no = find_map_sheet(198500.0, 453500.0, MapScale.SCALE_5000, features)
    assert sheet_no == "358051"


def test_find_map_sheet_respects_scale_filter():
    features = load_index(FIXTURE_PATH)
    sheet_no = find_map_sheet(198200.0, 453200.0, MapScale.SCALE_1000, features)
    assert sheet_no == "35805025"


def test_find_map_sheet_raises_when_point_outside_all_sheets():
    features = load_index(FIXTURE_PATH)
    with pytest.raises(ValueError):
        find_map_sheet(0.0, 0.0, MapScale.SCALE_5000, features)


def test_find_map_sheet_raises_when_point_in_bounds_but_wrong_scale():
    features = load_index(FIXTURE_PATH)
    with pytest.raises(ValueError):
        find_map_sheet(198700.0, 453700.0, MapScale.SCALE_1000, features)
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_map_sheet_index.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.map_sheet_index'`

- [ ] **Step 4: map_sheet_index.py 구현**

```python
# src/jibeon_cad_tool/map_sheet_index.py
import json
from pathlib import Path

from shapely.geometry import Point, shape

from .models import MapScale


def load_index(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def find_map_sheet(x: float, y: float, scale: MapScale, features: list[dict]) -> str:
    point = Point(x, y)
    for feature in features:
        if feature["properties"].get("scale") != scale.value:
            continue
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            return feature["properties"]["sheet_no"]
    raise ValueError(f"좌표 ({x}, {y})를 포함하는 {scale.value} 도엽을 찾을 수 없습니다")
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_map_sheet_index.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/map_sheet_index.py tests/test_map_sheet_index.py tests/fixtures/map_sheet_index_fixture.geojson
git commit -m "feat: add coordinate-to-map-sheet spatial lookup"
```

---

### Task 4: 브이월드 검색 real-mode (`crs` 파라미터 반영)

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/vworld_client.py`
- Modify: `jibeon_cad_tool/tests/test_vworld_client.py`

**Interfaces:**
- Consumes: 없음 (기존 `VWorldClient.search_parcel` 시그니처 유지)
- Produces: 동일 시그니처, 요청 파라미터에 `crs=EPSG:5186` 추가됨

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_vworld_client.py`에 추가)**

파일 상단 import에 `requests_mock`을 인자로 받는 테스트를 추가하기 위해 별도 import는 필요 없음(pytest-requests-mock 플러그인이 `requests_mock` fixture를 자동 제공). 파일 맨 아래에 추가:

```python
from jibeon_cad_tool.clients.vworld_client import VWORLD_SEARCH_URL


def test_search_parcel_real_mode_sends_crs_param(requests_mock):
    requests_mock.get(
        VWORLD_SEARCH_URL,
        json={
            "response": {
                "result": {
                    "items": [
                        {
                            "id": "1111010100100010000",
                            "address": {"road": "서울특별시 종로구 1"},
                            "point": {"x": "198000.0", "y": "453000.0"},
                        }
                    ]
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    result = client.search_parcel("서울특별시 종로구 1")

    assert result.pnu == "1111010100100010000"
    assert result.coord_system == CoordSystem.GRS80_MID
    sent_crs = requests_mock.last_request.qs.get("crs")
    assert sent_crs == ["epsg:5186"]


def test_search_parcel_real_mode_raises_when_no_items(requests_mock):
    requests_mock.get(
        VWORLD_SEARCH_URL,
        json={"response": {"result": {"items": []}}},
    )

    client = VWorldClient(api_key="real-key", use_mock=False)

    with pytest.raises(ValueError):
        client.search_parcel("존재하지 않는 주소")
```

`tests/test_vworld_client.py` 파일 상단에 `import pytest`가 없다면 추가한다 (기존 파일에 이미 있을 가능성이 높음 — 있으면 중복 추가하지 않는다).

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_vworld_client.py -v`
Expected: FAIL — `test_search_parcel_real_mode_sends_crs_param`에서 `assert sent_crs == ["epsg:5186"]`가 `None == [...]`로 실패 (아직 `crs` 파라미터를 보내지 않으므로)

- [ ] **Step 3: vworld_client.py의 `search_parcel` 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/vworld_client.py`의 `search_parcel` 메서드에서 `params` 딕셔너리에 `crs` 키를 추가:

```python
    def search_parcel(self, address: str) -> ParcelSearchResult:
        if self.use_mock:
            return mock_data.mock_search_parcel(address)

        params = {
            "service": "search",
            "request": "search",
            "query": address,
            "type": "address",
            "category": "parcel",
            "format": "json",
            "crs": "EPSG:5186",
            "key": self.api_key,
        }
        response = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_search_response(response.json(), address)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_vworld_client.py -v`
Expected: PASS (전체)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/vworld_client.py tests/test_vworld_client.py
git commit -m "fix: pin VWorld search response CRS to EPSG:5186 via request param"
```

---

### Task 5: 브이월드 지적도 real-mode (Data API 연동)

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/vworld_client.py`
- Modify: `jibeon_cad_tool/tests/test_vworld_client.py`

**Interfaces:**
- Consumes: `ParcelSearchResult` from `jibeon_cad_tool.models`
- Produces: `VWorldClient.download_cadastral(self, result: ParcelSearchResult) -> tuple[list[Polygon], int]` real-mode 구현 (반환 형식은 mock-mode와 동일하게 유지)

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_vworld_client.py`에 추가)**

```python
from jibeon_cad_tool.clients.vworld_client import VWORLD_DATA_URL


def test_download_cadastral_real_mode_parses_feature_collection(requests_mock):
    search_result = ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={
            "response": {
                "result": {
                    "featureCollection": {
                        "features": [
                            {
                                "properties": {"pnu": "1111010100100010000"},
                                "geometry": {
                                    "coordinates": [
                                        [[197990.0, 452990.0], [198010.0, 452990.0], [198010.0, 453010.0], [197990.0, 453010.0], [197990.0, 452990.0]]
                                    ]
                                },
                            },
                            {
                                "properties": {"pnu": "1111010100100020000"},
                                "geometry": {
                                    "coordinates": [
                                        [[198050.0, 452990.0], [198070.0, 452990.0], [198070.0, 453010.0], [198050.0, 453010.0], [198050.0, 452990.0]]
                                    ]
                                },
                            },
                        ]
                    }
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    parcels, target_index = client.download_cadastral(search_result)

    assert len(parcels) == 2
    assert target_index == 0
    assert parcels[0].contains(parcels[0].centroid)


def test_download_cadastral_real_mode_falls_back_to_spatial_containment(requests_mock):
    search_result = ParcelSearchResult(
        pnu="9999999999999999999", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={
            "response": {
                "result": {
                    "featureCollection": {
                        "features": [
                            {
                                "properties": {"pnu": "1111010100100010000"},
                                "geometry": {
                                    "coordinates": [
                                        [[197990.0, 452990.0], [198010.0, 452990.0], [198010.0, 453010.0], [197990.0, 453010.0], [197990.0, 452990.0]]
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    parcels, target_index = client.download_cadastral(search_result)

    assert target_index == 0


def test_download_cadastral_real_mode_raises_when_no_features(requests_mock):
    search_result = ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={"response": {"result": {"featureCollection": {"features": []}}}},
    )

    client = VWorldClient(api_key="real-key", use_mock=False)

    with pytest.raises(ValueError):
        client.download_cadastral(search_result)
```

`tests/test_vworld_client.py` 상단 import에 `ParcelSearchResult`, `CoordSystem`이 이미 있는지 확인하고 없으면 추가한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_vworld_client.py -v`
Expected: FAIL — `download_cadastral`이 여전히 `NotImplementedError`를 던지므로 새 테스트 3개가 실패

- [ ] **Step 3: vworld_client.py 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/vworld_client.py` 상단 import를 다음과 같이 수정:

```python
import os

import requests
from shapely.geometry import Point, Polygon

from ..models import CoordSystem, ParcelSearchResult
from . import mock_data

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
```

`download_cadastral` 메서드를 다음과 같이 교체:

```python
    def download_cadastral(self, result: ParcelSearchResult) -> tuple[list, int]:
        if self.use_mock:
            return mock_data.mock_cadastral_parcels(result)

        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN",
            "key": self.api_key,
            "geomFilter": f"POINT({result.x} {result.y})",
            "format": "json",
            "crs": "EPSG:5186",
            "size": "100",
        }
        response = requests.get(VWORLD_DATA_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_cadastral_response(response.json(), result)
```

파일 맨 아래, `_parse_search_response` 뒤에 다음 함수를 추가:

```python
def _parse_cadastral_response(data: dict, result: ParcelSearchResult) -> tuple[list[Polygon], int]:
    features = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
    if not features:
        raise ValueError(f"'{result.pnu}' 주변에서 지적 필지를 찾을 수 없습니다")

    parcels: list[Polygon] = []
    target_index = None
    for idx, feature in enumerate(features):
        coords = feature["geometry"]["coordinates"][0]
        polygon = Polygon(coords)
        parcels.append(polygon)
        if feature.get("properties", {}).get("pnu") == result.pnu:
            target_index = idx

    if target_index is None:
        point = Point(result.x, result.y)
        for idx, polygon in enumerate(parcels):
            if polygon.contains(point):
                target_index = idx
                break

    if target_index is None:
        raise ValueError(f"'{result.pnu}'에 해당하는 필지를 찾지 못했습니다")

    return parcels, target_index
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_vworld_client.py -v`
Expected: PASS (전체)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/vworld_client.py tests/test_vworld_client.py
git commit -m "feat: implement real VWorld cadastral parcel download via Data API"
```

---

### Task 6: NGII 셀렉터 설정 로더 (`ngii_selectors.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_selectors.py`
- Create: `jibeon_cad_tool/config/ngii_selectors.json`
- Test: `jibeon_cad_tool/tests/test_ngii_selectors.py`

**Interfaces:**
- Produces:
  - `NgiiSelectors` 데이터클래스 — 필드: `login_url: str`, `login_trigger_selector: str`, `username_selector: str`, `password_selector: str`, `login_submit_selector: str`, `catalog_url: str`, `sido_select_selector: str`, `scale_select_selector: str`, `sheet_no_input_selector: str`, `search_button_selector: str`, `cart_add_selector: str`, `request_submit_selector: str`, `download_link_selector: str`, `request_status_selector: str`
  - `load_selectors(path: Path) -> NgiiSelectors`

- [ ] **Step 1: `config/ngii_selectors.json` 작성 (사용자 캡처 전 기본값)**

```json
{
  "login_url": "https://map.ngii.go.kr",
  "login_trigger_selector": "PLACEHOLDER_로그인_버튼_셀렉터_playwright_codegen으로_캡처",
  "username_selector": "PLACEHOLDER_아이디_입력창_셀렉터",
  "password_selector": "PLACEHOLDER_비밀번호_입력창_셀렉터",
  "login_submit_selector": "PLACEHOLDER_로그인_제출_버튼_셀렉터",
  "catalog_url": "https://map.ngii.go.kr/pd/ctlsSvc/ctlsSvc.do",
  "sido_select_selector": "PLACEHOLDER_시도_선택_셀렉터",
  "scale_select_selector": "PLACEHOLDER_축척_선택_셀렉터",
  "sheet_no_input_selector": "PLACEHOLDER_도엽번호_입력_셀렉터",
  "search_button_selector": "PLACEHOLDER_검색_버튼_셀렉터",
  "cart_add_selector": "PLACEHOLDER_장바구니_담기_버튼_셀렉터",
  "request_submit_selector": "PLACEHOLDER_신청_제출_버튼_셀렉터",
  "download_link_selector": "PLACEHOLDER_다운로드_링크_셀렉터",
  "request_status_selector": "PLACEHOLDER_신청_상태_표시_셀렉터"
}
```

이 파일의 `login_url`과 `catalog_url`은 이 계획을 작성하며 실사이트에서 확인된 실제 값이다. 그 외 `PLACEHOLDER_`로 시작하는 값들은 사용자가 자신의 계정으로 로그인한 상태에서 `playwright codegen https://map.ngii.go.kr`를 실행해 직접 캡처해 채워야 한다 (설계 문서의 미해결 항목).

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_ngii_selectors.py
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_selectors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.clients.ngii_selectors'`

- [ ] **Step 4: ngii_selectors.py 구현**

```python
# src/jibeon_cad_tool/clients/ngii_selectors.py
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
    sido_select_selector: str
    scale_select_selector: str
    sheet_no_input_selector: str
    search_button_selector: str
    cart_add_selector: str
    request_submit_selector: str
    download_link_selector: str
    request_status_selector: str


def load_selectors(path: Path) -> NgiiSelectors:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return NgiiSelectors(**data)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_selectors.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add config/ngii_selectors.json src/jibeon_cad_tool/clients/ngii_selectors.py tests/test_ngii_selectors.py
git commit -m "feat: add NGII UI selector config loader"
```

---

### Task 7: `NgiiWebClient` — 로그인

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`
- Test: `jibeon_cad_tool/tests/test_ngii_web_client.py`

**Interfaces:**
- Consumes: `NgiiSelectors`, `load_selectors` from `jibeon_cad_tool.clients.ngii_selectors`; `CoordSystem`, `MapScale`, `ParcelSearchResult` from `jibeon_cad_tool.models`; `RasterDownloadResult` from `jibeon_cad_tool.clients.ngii_client` (재사용, 새로 정의하지 않음)
- Produces:
  - `NgiiWebClient(username: str = None, password: str = None, use_mock: bool = None, selectors: NgiiSelectors = None)` — `use_mock` 자동 감지: `NGII_USERNAME`/`NGII_PASSWORD` 둘 다 없으면 목업
  - `NgiiWebClient._login(page) -> None` — 내부 메서드. `page`는 Playwright `Page` 객체(또는 이를 흉내내는 테스트 더블). 로그인 실패 시 `RuntimeError`를 던짐 (재시도 없음)

이 태스크는 `NgiiWebClient`의 로그인 부분만 구현한다. 목업 모드의 `download_topo`/`download_ortho`는 Task 8에서 구현한다 — 이 태스크에서는 `_login`만 완성하고, 아직 연결되지 않은 다운로드 메서드는 만들지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_ngii_web_client.py
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.clients.ngii_web_client'`

- [ ] **Step 3: ngii_web_client.py 구현 (로그인 부분)**

```python
# src/jibeon_cad_tool/clients/ngii_web_client.py
import os
from pathlib import Path

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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/ngii_web_client.py tests/test_ngii_web_client.py
git commit -m "feat: add NgiiWebClient login flow with mock-mode auto-detection"
```

---

### Task 8: `NgiiWebClient` — 카탈로그 검색·신청·다운로드 (수치지형도 동기, 정사영상 폴링)

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`
- Modify: `jibeon_cad_tool/tests/test_ngii_web_client.py`

**Interfaces:**
- Consumes: `ParcelSearchResult`, `CoordSystem`, `MapScale` from `jibeon_cad_tool.models`; `find_map_sheet` from `jibeon_cad_tool.map_sheet_index`; `RasterDownloadResult` from `jibeon_cad_tool.clients.ngii_client`
- Produces:
  - `NgiiWebClient.download_topo(result: ParcelSearchResult, coord_system: CoordSystem, map_scale: MapScale, sheet_features: list[dict], output_path: str) -> RasterDownloadResult` — mock 모드는 기존 `NgiiClient`와 동일한 텍스트 스텁 작성, real 모드는 Playwright로 로그인→검색→장바구니→신청→즉시 다운로드
  - `NgiiWebClient.download_ortho(result: ParcelSearchResult, coord_system: CoordSystem, map_scale: MapScale, sheet_features: list[dict], output_path: str, poll_interval_seconds: float = 15.0, timeout_seconds: float = 600.0) -> RasterDownloadResult | None` — mock 모드는 텍스트 스텁, real 모드는 신청 후 폴링. 타임아웃 시 예외를 던지지 않고 `None`을 반환(파이프라인이 "다운로드 대기 중" 상태로 처리하도록)

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_ngii_web_client.py`에 추가)**

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
```

이 테스트 파일 상단에 `from unittest.mock import MagicMock`이 이미 Task 7에서 추가되어 있으므로 중복 추가하지 않는다. `make_selectors` 헬퍼는 Task 7에서 이미 정의되어 있으므로 재사용한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: FAIL — `download_topo`/`download_ortho`가 아직 정의되지 않아 `AttributeError`

- [ ] **Step 3: ngii_web_client.py에 다운로드 메서드 추가**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py` 상단 import를 다음과 같이 확장:

```python
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..models import CoordSystem, MapScale, ParcelSearchResult
from ..map_sheet_index import find_map_sheet
from .ngii_client import RasterDownloadResult
from .ngii_selectors import NgiiSelectors, load_selectors
```

`_login` 메서드 뒤, 클래스 안에 다음 메서드들을 추가:

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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: PASS (전체 — 로그인 테스트 4개 + 이번 태스크에서 추가한 4개)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/ngii_web_client.py tests/test_ngii_web_client.py
git commit -m "feat: implement NgiiWebClient catalog search, request, and download/polling"
```

---

### Task 9: 파이프라인에 도엽 조회 + `NgiiWebClient` 연동

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/pipeline.py`
- Modify: `jibeon_cad_tool/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `NgiiWebClient` from `jibeon_cad_tool.clients.ngii_web_client`; `find_map_sheet`, `load_index` from `jibeon_cad_tool.map_sheet_index`
- Produces: `run_pipeline`이 `ngii_client` 매개변수로 `NgiiWebClient` 인스턴스(또는 호환 인터페이스)를 받고, `include_topo`/`include_ortho`일 때 `download_topo`/`download_ortho`에 `map_scale`과 도엽 인덱스 `features`를 전달. `download_ortho`가 `None`을 반환하면 `ortho_path`는 `None`으로 유지하고 로그에 대기 상태를 남김 (파이프라인은 실패하지 않음)

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_pipeline.py`에 추가)**

```python
from jibeon_cad_tool.clients.ngii_web_client import NgiiWebClient
from jibeon_cad_tool.models import MapScale


def test_run_pipeline_passes_map_scale_and_handles_pending_ortho(tmp_path, monkeypatch):
    class _StubNgiiClient:
        def __init__(self):
            self.use_mock = True

        def download_topo(self, result, coord_system, map_scale, sheet_features, output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("TOPO stub\n")
            from jibeon_cad_tool.clients.ngii_client import RasterDownloadResult
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

        def download_ortho(self, result, coord_system, map_scale, sheet_features, output_path, **_kwargs):
            return None

    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        map_scale=MapScale.SCALE_5000,
        include_topo=True,
        include_ortho=True,
    )
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=_StubNgiiClient(),
    )

    assert result.topo_path is not None
    assert result.ortho_path is None
    assert any("대기" in line for line in result.log)
```

`tests/test_pipeline.py` 상단 import에 `MapScale`이 없다면 `from jibeon_cad_tool.models import ...` 줄에 추가한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_pipeline.py -v`
Expected: FAIL — 기존 `run_pipeline`이 `ngii_client.download_topo`/`download_ortho`를 옛 시그니처(`result, coord_system, output_path`)로 호출하므로 `_StubNgiiClient`의 새 시그니처와 맞지 않아 `TypeError`

- [ ] **Step 3: pipeline.py 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/pipeline.py`의 현재 내용 중 상단 import는 다음과 같다:

```python
import os
from dataclasses import dataclass

from shapely.geometry import Polygon

from .clients.ngii_client import NgiiClient
from .clients.vworld_client import VWorldClient
from .coords import transform_coords
from .dxf_export import build_cadastral_dxf
from .geometry import make_buffer_box
from .models import ExportOptions
```

다음과 같이 교체 (`NgiiClient` → `NgiiWebClient`, `Path` 추가):

```python
import os
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Polygon

from .clients.ngii_web_client import NgiiWebClient
from .clients.vworld_client import VWorldClient
from .coords import transform_coords
from .dxf_export import build_cadastral_dxf
from .geometry import make_buffer_box
from .models import ExportOptions
```

`run_pipeline` 시그니처와 첫 두 줄(현재):

```python
def run_pipeline(
    address: str,
    options: ExportOptions,
    output_dir: str,
    vworld_client: VWorldClient | None = None,
    ngii_client: NgiiClient | None = None,
) -> PipelineResult:
    vworld_client = vworld_client or VWorldClient()
    ngii_client = ngii_client or NgiiClient()
```

다음과 같이 교체:

```python
def run_pipeline(
    address: str,
    options: ExportOptions,
    output_dir: str,
    vworld_client: VWorldClient | None = None,
    ngii_client: NgiiWebClient | None = None,
) -> PipelineResult:
    vworld_client = vworld_client or VWorldClient()
    ngii_client = ngii_client or NgiiWebClient()
```

파일 하단의 현재 topo/ortho 블록(정확히 이 8줄):

```python
    topo_path = None
    ortho_path = None
    if options.include_topo:
        log.append("지형도 다운로드")
        topo_path = os.path.join(output_dir, f"{search_result.pnu}_topo.txt")
        ngii_client.download_topo(search_result, options.coord_system, topo_path)
    if options.include_ortho:
        log.append("정사영상 다운로드")
        ortho_path = os.path.join(output_dir, f"{search_result.pnu}_ortho.txt")
        ngii_client.download_ortho(search_result, options.coord_system, ortho_path)
```

다음과 같이 교체:

```python
    topo_path = None
    ortho_path = None
    if options.include_topo or options.include_ortho:
        sheet_features = _load_sheet_features_for_client(ngii_client)

    if options.include_topo:
        log.append("지형도 다운로드")
        topo_path = os.path.join(output_dir, f"{search_result.pnu}_topo.txt")
        ngii_client.download_topo(
            search_result, options.coord_system, options.map_scale, sheet_features, topo_path
        )
    if options.include_ortho:
        log.append("정사영상 다운로드")
        ortho_output_path = os.path.join(output_dir, f"{search_result.pnu}_ortho.txt")
        ortho_result = ngii_client.download_ortho(
            search_result, options.coord_system, options.map_scale, sheet_features, ortho_output_path
        )
        if ortho_result is not None:
            ortho_path = ortho_result.file_path
        else:
            log.append("정사영상 신청 완료 — 승인 대기 중이라 지금은 다운로드하지 못했습니다. 나중에 국토정보플랫폼에서 직접 확인하세요")
```

파일 맨 아래(마지막 `return PipelineResult(...)` 뒤)에 헬퍼 함수를 추가한다:

```python


def _load_sheet_features_for_client(ngii_client) -> list[dict]:
    if getattr(ngii_client, "use_mock", True):
        return []
    from .map_sheet_index import load_index

    default_index_path = Path(__file__).resolve().parent.parent.parent / "data" / "map_sheet_index_fixture.geojson"
    return load_index(default_index_path)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_pipeline.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 기존 `test_pipeline.py`의 `NgiiClient` 사용을 `NgiiWebClient`로 교체**

`pipeline.py`가 이제 `NgiiWebClient`를 기본 클라이언트로 쓰므로, 기존 테스트 3개가 주입하던 `NgiiClient(use_mock=True)`도 `NgiiWebClient(use_mock=True)`로 맞춰야 한다 (두 클래스 모두 mock 모드에서는 5개 인자 시그니처 `(result, coord_system, map_scale, sheet_features, output_path)`를 받도록 이미 통일되어 있으나, `pipeline.py`가 항상 `NgiiWebClient`의 이 시그니처로 호출하므로 `NgiiClient` 인스턴스를 넘기면 옛 3개 인자 시그니처와 충돌한다).

`jibeon_cad_tool/tests/test_pipeline.py` 상단 import를 다음과 같이 교체:

```python
import os

from jibeon_cad_tool.models import BorderShape, CoordSystem, ExportOptions
from jibeon_cad_tool.clients.vworld_client import VWorldClient
from jibeon_cad_tool.clients.ngii_web_client import NgiiWebClient
from jibeon_cad_tool.pipeline import run_pipeline
```

`test_run_pipeline_cadastral_only`, `test_run_pipeline_with_topo_and_ortho`, `test_run_pipeline_logs_each_stage` 세 함수에서 각각 `ngii_client=NgiiClient(use_mock=True)`를 `ngii_client=NgiiWebClient(use_mock=True)`로 교체한다 (총 3곳).

기존 `tests/test_ngii_client.py`와 `src/jibeon_cad_tool/clients/ngii_client.py`는 삭제하지 않고 그대로 남겨둔다 (해당 파일들의 자체 테스트는 계속 통과해야 하며, `RasterDownloadResult`를 `ngii_web_client.py`가 그대로 import해서 재사용하므로 삭제하면 안 된다). `pipeline.py`와 `tests/test_pipeline.py`만 `NgiiWebClient`를 사용하도록 정리한다.

- [ ] **Step 6: 전체 스위트 회귀 확인**

Run: `cd jibeon_cad_tool && pytest -v`
Expected: 전체 PASS (0 실패)

- [ ] **Step 7: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: wire map-sheet lookup and NgiiWebClient into pipeline, handle pending ortho"
```

---

### Task 10: UI에 축척 선택 드롭다운 추가

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/ui/main_window.py`
- Modify: `jibeon_cad_tool/tests/test_ui_main_window.py`

**Interfaces:**
- Produces: `MainWindow.map_scale_combo` (QComboBox) — `MapScale`의 모든 멤버를 한국어 라벨과 함께 표시, 기본 선택은 `MapScale.SCALE_5000`. `collect_export_options()`가 반환하는 `ExportOptions.map_scale`이 이 콤보박스의 현재 선택값을 반영

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_ui_main_window.py`에 추가)**

```python
from jibeon_cad_tool.models import MapScale


def test_main_window_has_map_scale_combo(qapp):
    window = MainWindow()
    assert window.map_scale_combo.count() == len(MapScale)
    assert window.map_scale_combo.currentData() == MapScale.SCALE_5000


def test_collect_export_options_reflects_map_scale_selection(qapp):
    window = MainWindow()
    window.map_scale_combo.setCurrentIndex(list(MapScale).index(MapScale.SCALE_1000))

    options = window.collect_export_options()

    assert options.map_scale == MapScale.SCALE_1000
```

`tests/test_ui_main_window.py` 상단 import에 `MapScale`이 없다면 `from jibeon_cad_tool.models import ...` 줄에 추가한다. `qapp` fixture는 기존 파일에 이미 정의되어 있으므로 재사용한다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ui_main_window.py -v`
Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute 'map_scale_combo'`

- [ ] **Step 3: main_window.py 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/ui/main_window.py` 상단 import를 수정:

```python
from ..models import BorderShape, CoordSystem, ExportOptions, MapScale
```

`COORD_SYSTEM_LABELS` 아래에 라벨 딕셔너리를 추가:

```python
MAP_SCALE_LABELS = {
    MapScale.SCALE_5000: "1:5,000",
    MapScale.SCALE_1000: "1:1,000",
}
```

`__init__` 안, `self.border_shape_combo` 생성 코드 뒤에 콤보박스를 추가:

```python
        self.map_scale_combo = QComboBox()
        for map_scale in MapScale:
            self.map_scale_combo.addItem(MAP_SCALE_LABELS[map_scale], map_scale)
```

`form_layout.addRow("도곽 형태:", self.border_shape_combo)` 바로 뒤에 다음 줄을 추가:

```python
        form_layout.addRow("축척:", self.map_scale_combo)
```

`collect_export_options` 메서드의 `return ExportOptions(...)` 안에 `map_scale` 인자를 추가:

```python
    def collect_export_options(self) -> ExportOptions:
        return ExportOptions(
            coord_system=self.coord_system_combo.currentData(),
            buffer_meters=float(self.buffer_input.text()),
            border_shape=self.border_shape_combo.currentData(),
            include_topo=self.include_topo_checkbox.isChecked(),
            include_ortho=self.include_ortho_checkbox.isChecked(),
            map_scale=self.map_scale_combo.currentData(),
        )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ui_main_window.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 전체 스위트 최종 회귀 확인**

Run: `cd jibeon_cad_tool && pytest -v`
Expected: 프로젝트 전체 테스트 PASS (0 실패)

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/ui/main_window.py tests/test_ui_main_window.py
git commit -m "feat: add map scale selection dropdown to main window"
```

---

## 후속 작업 (이 플랜 범위 밖)

- `config/ngii_selectors.json`의 `PLACEHOLDER_` 값들을 사용자가 `playwright codegen`으로 직접 캡처해 실제 셀렉터로 교체
- 도엽코드 인덱스의 실제 전국 데이터셋(공공데이터포털 원본)을 내려받아 `data/map_sheet_index_fixture.geojson`(테스트용 소규모 샘플)과 별도로 `data/map_sheet_index.geojson`(실 운영용 전체 인덱스)으로 배치하고, `pipeline.py`의 `_load_sheet_features_for_client`가 이를 사용하도록 경로 전환
- NGII 로그인 방식이 정부 통합로그인(anyID) 위젯이라 일반 아이디/비밀번호 폼과 다르게 동작할 경우, `_login`의 셀렉터 기반 흐름이 아니라 커스텀 엘리먼트/iframe 대응 로직이 추가로 필요할 수 있음 — 사용자 캡처 결과에 따라 재검토
- 정사영상 승인 대기가 타임아웃을 넘겨 `None`이 반환된 경우, 나중에 사용자가 수동으로 확인한 파일을 파이프라인 결과에 연결할 수 있는 UI(예: "정사영상 나중에 추가" 버튼)는 이번 범위에 없음
- Playwright 자동화의 실제 동작(로그인, 검색, 신청, 다운로드)은 사용자 계정으로 수동 검증 필요 — 이 플랜의 자동화 테스트는 모두 Playwright `Page`를 모킹한 단위 테스트이며 실 사이트 종단 테스트가 아님
