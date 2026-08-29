# 지번 기반 지적도/지형도/정사영상 CAD 내보내기 도구 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지번을 입력하면 브이월드/국토정보플랫폼에서 지적도·지형도·정사영상을 검색·다운로드하고, 좌표계를 통일하고, 대상 필지를 강조·클리핑·도곽 처리한 뒤 CAD(DXF)/이미지 파일로 내보내는 PySide6 데스크톱 앱을 구현한다.

**Architecture:** `src/jibeon_cad_tool/` 아래에 순수 함수 위주의 코어 모듈(좌표 변환, 지오메트리, DXF 출력)과 외부 API 클라이언트(브이월드/국토정보플랫폼, 목업 모드 지원)를 분리하고, `pipeline.py`가 이들을 순서대로 호출해 전체 흐름을 조립한다. UI(`ui/main_window.py`)는 `pipeline.run_pipeline()`을 백그라운드 스레드에서 호출하는 얇은 래퍼로만 존재한다.

**Tech Stack:** Python 3.11+, PySide6, ezdxf, pyproj, shapely, requests, pytest

## Global Constraints

- 좌표계는 `docs/superpowers/specs/2026-08-30-jibeon-cad-export-design.md`에 정의된 `CoordSystem` 값(EPSG:5186 기본, 5185/5187/5179 선택 가능)을 그대로 사용한다.
- API 키가 없는 개발 단계에서는 모든 외부 호출을 목업 모드로 동작시킨다 (`VWORLD_API_KEY`/`NGII_API_KEY` 환경변수 미설정 시 자동 목업).
- CAD 출력은 지적도/지형도를 DXF로, 정사영상은 별도 파일(목업 단계에서는 텍스트 스텁, 실 연동 시 GeoTIFF)로 각각 따로 저장한다 — 단일 파일로 합치지 않는다.
- 버퍼 거리와 도곽 형태(사각형/원형)는 기본값을 제공하되 UI에서 수정 가능해야 한다.

---

## 파일 구조

```
jibeon_cad_tool/
├── requirements.txt
├── pytest.ini
├── src/
│   └── jibeon_cad_tool/
│       ├── __init__.py
│       ├── models.py          # CoordSystem, BorderShape, ParcelSearchResult, ExportOptions
│       ├── coords.py          # pyproj 좌표 변환 래퍼
│       ├── geometry.py        # 버퍼박스/클리핑/도곽 shapely 로직
│       ├── dxf_export.py      # ezdxf 기반 DXF 생성 (레이어/강조/클리핑/도곽)
│       ├── pipeline.py        # 전체 파이프라인 오케스트레이션
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── mock_data.py       # 브이월드/국토정보플랫폼 목업 응답
│       │   ├── vworld_client.py   # 브이월드 검색/지적도 다운로드 클라이언트
│       │   └── ngii_client.py     # 국토정보플랫폼 지형도/정사영상 클라이언트
│       └── ui/
│           ├── __init__.py
│           ├── main_window.py     # PySide6 메인 윈도우
│           └── app.py             # 앱 엔트리포인트
└── tests/
    ├── test_coords.py
    ├── test_geometry.py
    ├── test_dxf_export.py
    ├── test_vworld_client.py
    ├── test_ngii_client.py
    ├── test_pipeline.py
    └── test_ui_main_window.py
```

---

### Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `jibeon_cad_tool/requirements.txt`
- Create: `jibeon_cad_tool/pytest.ini`
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/__init__.py`
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/clients/__init__.py`
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/ui/__init__.py`
- Create: `jibeon_cad_tool/tests/__init__.py`

**Interfaces:**
- Produces: 설치 가능한 패키지 `jibeon_cad_tool` (편집 가능 설치), pytest가 `src/` 레이아웃을 찾을 수 있는 설정

- [ ] **Step 1: 디렉터리와 requirements.txt 생성**

```text
ezdxf>=1.3.0
pyproj>=3.6.0
shapely>=2.0.0
requests>=2.31.0
PySide6>=6.7.0
pytest>=8.0.0
```

- [ ] **Step 2: pytest.ini 작성**

```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 3: 빈 `__init__.py` 파일들 생성**

`src/jibeon_cad_tool/__init__.py`, `src/jibeon_cad_tool/clients/__init__.py`, `src/jibeon_cad_tool/ui/__init__.py`, `tests/__init__.py` 모두 빈 파일로 생성.

- [ ] **Step 4: 의존성 설치**

Run: `cd jibeon_cad_tool && pip install -r requirements.txt`
Expected: 설치 완료, 에러 없음

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add requirements.txt pytest.ini src tests
git commit -m "chore: scaffold jibeon_cad_tool project structure"
```

---

### Task 2: 데이터 모델 (`models.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/models.py`
- Test: `jibeon_cad_tool/tests/test_models.py`

**Interfaces:**
- Produces:
  - `CoordSystem(Enum)` — `GRS80_MID = "EPSG:5186"`, `GRS80_WEST = "EPSG:5185"`, `GRS80_EAST = "EPSG:5187"`, `UTMK = "EPSG:5179"`
  - `BorderShape(Enum)` — `RECTANGLE = "rectangle"`, `CIRCLE = "circle"`
  - `ParcelSearchResult(pnu: str, address: str, x: float, y: float, coord_system: CoordSystem)`
  - `ExportOptions(coord_system: CoordSystem, buffer_meters: float = 100.0, border_shape: BorderShape = BorderShape.RECTANGLE, include_topo: bool = False, include_ortho: bool = False)`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_models.py
from jibeon_cad_tool.models import CoordSystem, BorderShape, ParcelSearchResult, ExportOptions


def test_coord_system_values():
    assert CoordSystem.GRS80_MID.value == "EPSG:5186"
    assert CoordSystem.UTMK.value == "EPSG:5179"


def test_export_options_defaults():
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    assert options.buffer_meters == 100.0
    assert options.border_shape == BorderShape.RECTANGLE
    assert options.include_topo is False
    assert options.include_ortho is False


def test_parcel_search_result_fields():
    result = ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    assert result.pnu == "1111010100100010000"
    assert result.x == 198000.0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.models'`

- [ ] **Step 3: models.py 구현**

```python
# src/jibeon_cad_tool/models.py
from dataclasses import dataclass
from enum import Enum


class CoordSystem(Enum):
    GRS80_MID = "EPSG:5186"
    GRS80_WEST = "EPSG:5185"
    GRS80_EAST = "EPSG:5187"
    UTMK = "EPSG:5179"


class BorderShape(Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"


@dataclass
class ParcelSearchResult:
    pnu: str
    address: str
    x: float
    y: float
    coord_system: CoordSystem


@dataclass
class ExportOptions:
    coord_system: CoordSystem
    buffer_meters: float = 100.0
    border_shape: BorderShape = BorderShape.RECTANGLE
    include_topo: bool = False
    include_ortho: bool = False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/models.py tests/test_models.py
git commit -m "feat: add core data models (CoordSystem, BorderShape, ParcelSearchResult, ExportOptions)"
```

---

### Task 3: 좌표 변환 (`coords.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/coords.py`
- Test: `jibeon_cad_tool/tests/test_coords.py`

**Interfaces:**
- Consumes: `CoordSystem` from `jibeon_cad_tool.models`
- Produces:
  - `transform_point(x: float, y: float, src: CoordSystem, dst: CoordSystem) -> tuple[float, float]`
  - `transform_coords(coords: list[tuple[float, float]], src: CoordSystem, dst: CoordSystem) -> list[tuple[float, float]]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_coords.py
import pytest
from jibeon_cad_tool.models import CoordSystem
from jibeon_cad_tool.coords import transform_point, transform_coords


def test_transform_point_identity_when_same_system():
    x, y = transform_point(198000.0, 453000.0, CoordSystem.GRS80_MID, CoordSystem.GRS80_MID)
    assert x == 198000.0
    assert y == 453000.0


def test_transform_point_round_trip():
    original_x, original_y = 198000.0, 453000.0
    tx, ty = transform_point(original_x, original_y, CoordSystem.GRS80_MID, CoordSystem.UTMK)
    back_x, back_y = transform_point(tx, ty, CoordSystem.UTMK, CoordSystem.GRS80_MID)
    assert back_x == pytest.approx(original_x, abs=0.01)
    assert back_y == pytest.approx(original_y, abs=0.01)
    assert (tx, ty) != (original_x, original_y)


def test_transform_coords_list():
    coords = [(198000.0, 453000.0), (198010.0, 453010.0)]
    result = transform_coords(coords, CoordSystem.GRS80_MID, CoordSystem.GRS80_MID)
    assert result == coords
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_coords.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.coords'`

- [ ] **Step 3: coords.py 구현**

```python
# src/jibeon_cad_tool/coords.py
from pyproj import Transformer

from .models import CoordSystem


def transform_point(x: float, y: float, src: CoordSystem, dst: CoordSystem) -> tuple[float, float]:
    if src == dst:
        return x, y
    transformer = Transformer.from_crs(src.value, dst.value, always_xy=True)
    return transformer.transform(x, y)


def transform_coords(
    coords: list[tuple[float, float]], src: CoordSystem, dst: CoordSystem
) -> list[tuple[float, float]]:
    if src == dst:
        return list(coords)
    transformer = Transformer.from_crs(src.value, dst.value, always_xy=True)
    return [transformer.transform(x, y) for x, y in coords]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_coords.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/coords.py tests/test_coords.py
git commit -m "feat: add pyproj-based coordinate transform module"
```

---

### Task 4: 지오메트리 — 버퍼박스/클리핑/도곽 (`geometry.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/geometry.py`
- Test: `jibeon_cad_tool/tests/test_geometry.py`

**Interfaces:**
- Consumes: `BorderShape` from `jibeon_cad_tool.models`
- Produces:
  - `make_buffer_box(center_x: float, center_y: float, buffer_meters: float) -> shapely.Polygon`
  - `clip_geometry(geometry, clip_box) -> shapely geometry` (intersection)
  - `make_border(center_x: float, center_y: float, buffer_meters: float, shape: BorderShape) -> shapely geometry`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_geometry.py
import pytest
from shapely.geometry import Polygon

from jibeon_cad_tool.models import BorderShape
from jibeon_cad_tool.geometry import make_buffer_box, clip_geometry, make_border


def test_make_buffer_box_dimensions():
    box = make_buffer_box(100.0, 200.0, 50.0)
    assert box.bounds == (50.0, 150.0, 150.0, 250.0)


def test_clip_geometry_intersection():
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    clip_box = Polygon([(50, 50), (150, 50), (150, 150), (50, 150)])
    result = clip_geometry(poly, clip_box)
    assert result.bounds == (50.0, 50.0, 100.0, 100.0)


def test_clip_geometry_no_overlap_returns_empty():
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    clip_box = Polygon([(100, 100), (110, 100), (110, 110), (100, 110)])
    result = clip_geometry(poly, clip_box)
    assert result.is_empty


def test_make_border_rectangle_matches_buffer_box():
    border = make_border(0.0, 0.0, 20.0, BorderShape.RECTANGLE)
    assert border.bounds == (-20.0, -20.0, 20.0, 20.0)


def test_make_border_circle_is_round():
    border = make_border(0.0, 0.0, 20.0, BorderShape.CIRCLE)
    assert border.geom_type == "Polygon"
    minx, miny, maxx, maxy = border.bounds
    assert maxx - minx == pytest.approx(40.0, abs=0.5)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.geometry'`

- [ ] **Step 3: geometry.py 구현**

```python
# src/jibeon_cad_tool/geometry.py
from shapely.geometry import Point, Polygon

from .models import BorderShape


def make_buffer_box(center_x: float, center_y: float, buffer_meters: float) -> Polygon:
    return Polygon([
        (center_x - buffer_meters, center_y - buffer_meters),
        (center_x + buffer_meters, center_y - buffer_meters),
        (center_x + buffer_meters, center_y + buffer_meters),
        (center_x - buffer_meters, center_y + buffer_meters),
    ])


def clip_geometry(geometry, clip_box: Polygon):
    return geometry.intersection(clip_box)


def make_border(center_x: float, center_y: float, buffer_meters: float, shape: BorderShape):
    if shape == BorderShape.CIRCLE:
        return Point(center_x, center_y).buffer(buffer_meters, resolution=64)
    return make_buffer_box(center_x, center_y, buffer_meters)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_geometry.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/geometry.py tests/test_geometry.py
git commit -m "feat: add buffer box, clipping, and border geometry helpers"
```

---

### Task 5: DXF 출력 (`dxf_export.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/dxf_export.py`
- Test: `jibeon_cad_tool/tests/test_dxf_export.py`

**Interfaces:**
- Consumes:
  - `clip_geometry`, `make_border` from `jibeon_cad_tool.geometry`
  - `BorderShape` from `jibeon_cad_tool.models`
- Produces:
  - `build_cadastral_dxf(parcels: list[shapely.Polygon], target_index: int, clip_box: shapely.Polygon, border_shape: BorderShape, center_x: float, center_y: float, buffer_meters: float, output_path: str) -> None`
  - 저장된 DXF는 레이어 `CADASTRAL`(일반 필지), `HIGHLIGHT`(대상 필지), `BORDER`(도곽)를 포함

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_dxf_export.py
import ezdxf
from shapely.geometry import Polygon

from jibeon_cad_tool.models import BorderShape
from jibeon_cad_tool.geometry import make_buffer_box
from jibeon_cad_tool.dxf_export import build_cadastral_dxf


def test_build_cadastral_dxf_creates_layers_and_highlight(tmp_path):
    target = Polygon([(90, 90), (110, 90), (110, 110), (90, 110)])
    neighbor = Polygon([(200, 200), (220, 200), (220, 220), (200, 220)])
    clip_box = make_buffer_box(100.0, 100.0, 50.0)
    output_path = str(tmp_path / "cadastral.dxf")

    build_cadastral_dxf(
        parcels=[target, neighbor],
        target_index=0,
        clip_box=clip_box,
        border_shape=BorderShape.RECTANGLE,
        center_x=100.0,
        center_y=100.0,
        buffer_meters=50.0,
        output_path=output_path,
    )

    doc = ezdxf.readfile(output_path)
    msp = doc.modelspace()
    layer_names = {layer.dxf.name for layer in doc.layers}
    assert {"CADASTRAL", "HIGHLIGHT", "BORDER"}.issubset(layer_names)

    highlight_entities = list(msp.query('LWPOLYLINE[layer=="HIGHLIGHT"]'))
    assert len(highlight_entities) == 1

    border_entities = list(msp.query('LWPOLYLINE[layer=="BORDER"]'))
    assert len(border_entities) == 1

    cadastral_entities = list(msp.query('LWPOLYLINE[layer=="CADASTRAL"]'))
    assert len(cadastral_entities) == 0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_dxf_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.dxf_export'`

- [ ] **Step 3: dxf_export.py 구현**

```python
# src/jibeon_cad_tool/dxf_export.py
import ezdxf
from shapely.geometry import Polygon

from .geometry import clip_geometry, make_border
from .models import BorderShape


def build_cadastral_dxf(
    parcels: list[Polygon],
    target_index: int,
    clip_box: Polygon,
    border_shape: BorderShape,
    center_x: float,
    center_y: float,
    buffer_meters: float,
    output_path: str,
) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add(name="CADASTRAL", color=7)
    doc.layers.add(name="HIGHLIGHT", color=1)
    doc.layers.add(name="BORDER", color=3)

    for idx, poly in enumerate(parcels):
        clipped = clip_geometry(poly, clip_box)
        if clipped.is_empty:
            continue
        layer = "HIGHLIGHT" if idx == target_index else "CADASTRAL"
        for ring_coords in _polygon_rings(clipped):
            msp.add_lwpolyline(ring_coords, dxfattribs={"layer": layer, "closed": True})

    border = make_border(center_x, center_y, buffer_meters, border_shape)
    for ring_coords in _polygon_rings(border):
        msp.add_lwpolyline(ring_coords, dxfattribs={"layer": "BORDER", "closed": True})

    doc.saveas(output_path)


def _polygon_rings(geometry):
    if geometry.geom_type == "Polygon":
        yield list(geometry.exterior.coords)
    elif geometry.geom_type == "MultiPolygon":
        for part in geometry.geoms:
            yield list(part.exterior.coords)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_dxf_export.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/dxf_export.py tests/test_dxf_export.py
git commit -m "feat: add DXF export with highlight/border layers"
```

---

### Task 6: 브이월드 클라이언트 + 목업 데이터

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/clients/mock_data.py`
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/clients/vworld_client.py`
- Test: `jibeon_cad_tool/tests/test_vworld_client.py`

**Interfaces:**
- Consumes: `ParcelSearchResult`, `CoordSystem` from `jibeon_cad_tool.models`
- Produces:
  - `mock_data.mock_search_parcel(address: str) -> ParcelSearchResult`
  - `mock_data.mock_cadastral_parcels(result: ParcelSearchResult, coord_system: CoordSystem) -> tuple[list[shapely.Polygon], int]` (필지 목록, 대상 필지 인덱스)
  - `VWorldClient(api_key: str = None, use_mock: bool = None)` with methods:
    - `search_parcel(address: str) -> ParcelSearchResult` (검색 결과 없으면 `ValueError`)
    - `download_cadastral(result: ParcelSearchResult, coord_system: CoordSystem) -> tuple[list[shapely.Polygon], int]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_vworld_client.py
import pytest

from jibeon_cad_tool.models import CoordSystem
from jibeon_cad_tool.clients import mock_data
from jibeon_cad_tool.clients.vworld_client import VWorldClient


def test_search_parcel_mock_mode_returns_result():
    client = VWorldClient(use_mock=True)
    result = client.search_parcel("서울특별시 종로구 1번지")
    assert result.address == "서울특별시 종로구 1번지"
    assert result.pnu
    assert result.coord_system == CoordSystem.GRS80_MID


def test_download_cadastral_mock_mode_includes_target_parcel():
    client = VWorldClient(use_mock=True)
    search_result = client.search_parcel("서울특별시 종로구 1번지")
    parcels, target_index = client.download_cadastral(search_result, CoordSystem.GRS80_MID)
    assert len(parcels) >= 1
    target = parcels[target_index]
    assert target.contains(target.centroid)


def test_download_cadastral_without_mock_raises_not_implemented():
    client = VWorldClient(api_key="dummy-key", use_mock=False)
    search_result = mock_data.mock_search_parcel("테스트")
    with pytest.raises(NotImplementedError):
        client.download_cadastral(search_result, CoordSystem.GRS80_MID)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_vworld_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.clients.vworld_client'`

- [ ] **Step 3: mock_data.py 구현**

```python
# src/jibeon_cad_tool/clients/mock_data.py
from shapely.geometry import Polygon

from ..models import CoordSystem, ParcelSearchResult


def mock_search_parcel(address: str) -> ParcelSearchResult:
    return ParcelSearchResult(
        pnu="1111010100100010000",
        address=address,
        x=198000.0,
        y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )


def mock_cadastral_parcels(
    result: ParcelSearchResult, coord_system: CoordSystem
) -> tuple[list[Polygon], int]:
    cx, cy = result.x, result.y
    target = Polygon([
        (cx - 10, cy - 10), (cx + 10, cy - 10),
        (cx + 10, cy + 10), (cx - 10, cy + 10),
    ])
    neighbor = Polygon([
        (cx + 15, cy - 10), (cx + 35, cy - 10),
        (cx + 35, cy + 10), (cx + 15, cy + 10),
    ])
    return [target, neighbor], 0
```

- [ ] **Step 4: vworld_client.py 구현**

```python
# src/jibeon_cad_tool/clients/vworld_client.py
import os

import requests

from ..models import CoordSystem, ParcelSearchResult
from . import mock_data

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"


class VWorldClient:
    def __init__(self, api_key: str | None = None, use_mock: bool | None = None):
        self.api_key = api_key or os.environ.get("VWORLD_API_KEY", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.api_key)

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
            "key": self.api_key,
        }
        response = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_search_response(response.json(), address)

    def download_cadastral(
        self, result: ParcelSearchResult, coord_system: CoordSystem
    ) -> tuple[list, int]:
        if self.use_mock:
            return mock_data.mock_cadastral_parcels(result, coord_system)
        raise NotImplementedError(
            "실 API 지적도 다운로드 엔드포인트는 API 키 발급 후 연동 예정"
        )


def _parse_search_response(data: dict, address: str) -> ParcelSearchResult:
    items = data.get("response", {}).get("result", {}).get("items", [])
    if not items:
        raise ValueError(f"'{address}'에 해당하는 지번을 찾을 수 없습니다")
    item = items[0]
    point = item["point"]
    return ParcelSearchResult(
        pnu=item.get("id", ""),
        address=item.get("address", {}).get("road", address),
        x=float(point["x"]),
        y=float(point["y"]),
        coord_system=CoordSystem.GRS80_MID,
    )
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_vworld_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/mock_data.py src/jibeon_cad_tool/clients/vworld_client.py tests/test_vworld_client.py
git commit -m "feat: add VWorld client with mock-mode search and cadastral download"
```

---

### Task 7: 국토정보플랫폼 클라이언트 (`ngii_client.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_client.py`
- Test: `jibeon_cad_tool/tests/test_ngii_client.py`

**Interfaces:**
- Consumes: `ParcelSearchResult`, `CoordSystem` from `jibeon_cad_tool.models`
- Produces:
  - `RasterDownloadResult(file_path: str, coord_system: CoordSystem)`
  - `NgiiClient(api_key: str = None, use_mock: bool = None)` with methods:
    - `download_topo(result: ParcelSearchResult, coord_system: CoordSystem, output_path: str) -> RasterDownloadResult`
    - `download_ortho(result: ParcelSearchResult, coord_system: CoordSystem, output_path: str) -> RasterDownloadResult`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_ngii_client.py
import os

import pytest

from jibeon_cad_tool.models import CoordSystem, ParcelSearchResult
from jibeon_cad_tool.clients.ngii_client import NgiiClient


@pytest.fixture
def search_result():
    return ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )


def test_download_topo_mock_mode_writes_file(tmp_path, search_result):
    client = NgiiClient(use_mock=True)
    output_path = str(tmp_path / "topo.txt")
    result = client.download_topo(search_result, CoordSystem.GRS80_MID, output_path)
    assert result.file_path == output_path
    assert os.path.exists(output_path)
    content = open(output_path, encoding="utf-8").read()
    assert "TOPO" in content
    assert search_result.pnu in content


def test_download_ortho_mock_mode_writes_file(tmp_path, search_result):
    client = NgiiClient(use_mock=True)
    output_path = str(tmp_path / "ortho.txt")
    result = client.download_ortho(search_result, CoordSystem.UTMK, output_path)
    assert result.coord_system == CoordSystem.UTMK
    content = open(output_path, encoding="utf-8").read()
    assert "ORTHO" in content


def test_download_topo_without_mock_raises_not_implemented(search_result):
    client = NgiiClient(api_key="dummy-key", use_mock=False)
    with pytest.raises(NotImplementedError):
        client.download_topo(search_result, CoordSystem.GRS80_MID, "unused.txt")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.clients.ngii_client'`

- [ ] **Step 3: ngii_client.py 구현**

```python
# src/jibeon_cad_tool/clients/ngii_client.py
import os
from dataclasses import dataclass

from ..models import CoordSystem, ParcelSearchResult


@dataclass
class RasterDownloadResult:
    file_path: str
    coord_system: CoordSystem


class NgiiClient:
    def __init__(self, api_key: str | None = None, use_mock: bool | None = None):
        self.api_key = api_key or os.environ.get("NGII_API_KEY", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.api_key)

    def download_topo(
        self, result: ParcelSearchResult, coord_system: CoordSystem, output_path: str
    ) -> RasterDownloadResult:
        if self.use_mock:
            _write_mock_raster_stub(output_path, "TOPO", result, coord_system)
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)
        raise NotImplementedError(
            "실 API 수치지형도 다운로드 엔드포인트는 API 키 발급 후 연동 예정"
        )

    def download_ortho(
        self, result: ParcelSearchResult, coord_system: CoordSystem, output_path: str
    ) -> RasterDownloadResult:
        if self.use_mock:
            _write_mock_raster_stub(output_path, "ORTHO", result, coord_system)
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)
        raise NotImplementedError(
            "실 API 정사영상 다운로드 엔드포인트는 API 키 발급 후 연동 예정"
        )


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

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/clients/ngii_client.py tests/test_ngii_client.py
git commit -m "feat: add NGII client with mock-mode topo/ortho download"
```

---

### Task 8: 파이프라인 오케스트레이션 (`pipeline.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/pipeline.py`
- Test: `jibeon_cad_tool/tests/test_pipeline.py`

**Interfaces:**
- Consumes:
  - `ExportOptions`, `CoordSystem` from `jibeon_cad_tool.models`
  - `VWorldClient` from `jibeon_cad_tool.clients.vworld_client`
  - `NgiiClient` from `jibeon_cad_tool.clients.ngii_client`
  - `transform_coords` from `jibeon_cad_tool.coords`
  - `make_buffer_box` from `jibeon_cad_tool.geometry`
  - `build_cadastral_dxf` from `jibeon_cad_tool.dxf_export`
- Produces:
  - `PipelineResult(cadastral_path: str, topo_path: str | None, ortho_path: str | None, log: list[str])`
  - `run_pipeline(address: str, options: ExportOptions, output_dir: str, vworld_client: VWorldClient = None, ngii_client: NgiiClient = None) -> PipelineResult`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_pipeline.py
import os

from jibeon_cad_tool.models import BorderShape, CoordSystem, ExportOptions
from jibeon_cad_tool.clients.vworld_client import VWorldClient
from jibeon_cad_tool.clients.ngii_client import NgiiClient
from jibeon_cad_tool.pipeline import run_pipeline


def test_run_pipeline_cadastral_only(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID, buffer_meters=30.0)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    assert os.path.exists(result.cadastral_path)
    assert result.topo_path is None
    assert result.ortho_path is None
    assert "완료" in result.log[-1]


def test_run_pipeline_with_topo_and_ortho(tmp_path):
    options = ExportOptions(
        coord_system=CoordSystem.UTMK,
        buffer_meters=50.0,
        border_shape=BorderShape.CIRCLE,
        include_topo=True,
        include_ortho=True,
    )
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    assert os.path.exists(result.cadastral_path)
    assert os.path.exists(result.topo_path)
    assert os.path.exists(result.ortho_path)


def test_run_pipeline_logs_each_stage(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    joined_log = " ".join(result.log)
    assert "검색" in joined_log
    assert "지적도 다운로드" in joined_log
    assert "좌표계 변환" in joined_log
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.pipeline'`

- [ ] **Step 3: pipeline.py 구현**

```python
# src/jibeon_cad_tool/pipeline.py
import os
from dataclasses import dataclass

from shapely.geometry import Polygon

from .clients.ngii_client import NgiiClient
from .clients.vworld_client import VWorldClient
from .coords import transform_coords
from .dxf_export import build_cadastral_dxf
from .geometry import make_buffer_box
from .models import ExportOptions


@dataclass
class PipelineResult:
    cadastral_path: str
    topo_path: str | None
    ortho_path: str | None
    log: list[str]


def run_pipeline(
    address: str,
    options: ExportOptions,
    output_dir: str,
    vworld_client: VWorldClient | None = None,
    ngii_client: NgiiClient | None = None,
) -> PipelineResult:
    vworld_client = vworld_client or VWorldClient()
    ngii_client = ngii_client or NgiiClient()
    log: list[str] = []
    os.makedirs(output_dir, exist_ok=True)

    log.append(f"검색: {address}")
    search_result = vworld_client.search_parcel(address)

    log.append("지적도 다운로드")
    parcels, target_index = vworld_client.download_cadastral(search_result, options.coord_system)

    log.append("좌표계 변환")
    transformed_parcels = [
        Polygon(transform_coords(list(poly.exterior.coords), search_result.coord_system, options.coord_system))
        for poly in parcels
    ]
    center_x, center_y = transform_coords(
        [(search_result.x, search_result.y)], search_result.coord_system, options.coord_system
    )[0]

    log.append("강조 표시 및 클리핑 및 도곽 생성 후 지적도 저장")
    clip_box = make_buffer_box(center_x, center_y, options.buffer_meters)
    cadastral_path = os.path.join(output_dir, "cadastral.dxf")
    build_cadastral_dxf(
        parcels=transformed_parcels,
        target_index=target_index,
        clip_box=clip_box,
        border_shape=options.border_shape,
        center_x=center_x,
        center_y=center_y,
        buffer_meters=options.buffer_meters,
        output_path=cadastral_path,
    )

    topo_path = None
    ortho_path = None
    if options.include_topo:
        log.append("지형도 다운로드")
        topo_path = os.path.join(output_dir, "topo.txt")
        ngii_client.download_topo(search_result, options.coord_system, topo_path)
    if options.include_ortho:
        log.append("정사영상 다운로드")
        ortho_path = os.path.join(output_dir, "ortho.txt")
        ngii_client.download_ortho(search_result, options.coord_system, ortho_path)

    log.append("완료")
    return PipelineResult(
        cadastral_path=cadastral_path, topo_path=topo_path, ortho_path=ortho_path, log=log
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/pipeline.py tests/test_pipeline.py
git commit -m "feat: add pipeline orchestration wiring search through export"
```

---

### Task 9: PySide6 메인 윈도우 (`ui/main_window.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/ui/main_window.py`
- Test: `jibeon_cad_tool/tests/test_ui_main_window.py`

**Interfaces:**
- Consumes:
  - `ExportOptions`, `CoordSystem`, `BorderShape` from `jibeon_cad_tool.models`
  - `run_pipeline`, `PipelineResult` from `jibeon_cad_tool.pipeline`
- Produces:
  - `MainWindow(QMainWindow)` with widgets accessible as attributes: `address_input` (QLineEdit), `search_button` (QPushButton), `coord_system_combo` (QComboBox), `include_topo_checkbox`/`include_ortho_checkbox` (QCheckBox), `buffer_input` (QLineEdit), `border_shape_combo` (QComboBox), `run_button` (QPushButton), `log_view` (QPlainTextEdit), `open_folder_button` (QPushButton)
  - `MainWindow.collect_export_options() -> ExportOptions` — 현재 폼 값으로 `ExportOptions` 생성
  - `MainWindow.append_log(message: str) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_ui_main_window.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from jibeon_cad_tool.models import BorderShape, CoordSystem
from jibeon_cad_tool.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_has_required_widgets(qapp):
    window = MainWindow()
    assert window.address_input is not None
    assert window.search_button is not None
    assert window.coord_system_combo.count() == len(CoordSystem)
    assert window.border_shape_combo.count() == len(BorderShape)
    assert window.run_button is not None
    assert window.log_view is not None


def test_collect_export_options_reflects_form_values(qapp):
    window = MainWindow()
    window.buffer_input.setText("75")
    window.include_topo_checkbox.setChecked(True)
    window.coord_system_combo.setCurrentIndex(
        list(CoordSystem).index(CoordSystem.UTMK)
    )
    window.border_shape_combo.setCurrentIndex(
        list(BorderShape).index(BorderShape.CIRCLE)
    )

    options = window.collect_export_options()

    assert options.buffer_meters == 75.0
    assert options.include_topo is True
    assert options.coord_system == CoordSystem.UTMK
    assert options.border_shape == BorderShape.CIRCLE


def test_append_log_adds_line_to_log_view(qapp):
    window = MainWindow()
    window.append_log("검색: 테스트 주소")
    assert "검색: 테스트 주소" in window.log_view.toPlainText()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ui_main_window.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.ui.main_window'`

- [ ] **Step 3: main_window.py 구현**

```python
# src/jibeon_cad_tool/ui/main_window.py
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import BorderShape, CoordSystem, ExportOptions
from ..pipeline import run_pipeline

COORD_SYSTEM_LABELS = {
    CoordSystem.GRS80_MID: "GRS80 중부원점 (EPSG:5186)",
    CoordSystem.GRS80_WEST: "GRS80 서부원점 (EPSG:5185)",
    CoordSystem.GRS80_EAST: "GRS80 동부원점 (EPSG:5187)",
    CoordSystem.UTMK: "UTM-K (EPSG:5179)",
}

BORDER_SHAPE_LABELS = {
    BorderShape.RECTANGLE: "사각형",
    BorderShape.CIRCLE: "원형",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("지번 기반 CAD 내보내기")
        self.output_dir = "."

        self.address_input = QLineEdit()
        self.search_button = QPushButton("검색")

        self.coord_system_combo = QComboBox()
        for coord_system in CoordSystem:
            self.coord_system_combo.addItem(COORD_SYSTEM_LABELS[coord_system], coord_system)

        self.include_topo_checkbox = QCheckBox("지형도 다운로드")
        self.include_ortho_checkbox = QCheckBox("정사영상 다운로드")

        self.buffer_input = QLineEdit("100")

        self.border_shape_combo = QComboBox()
        for border_shape in BorderShape:
            self.border_shape_combo.addItem(BORDER_SHAPE_LABELS[border_shape], border_shape)

        self.run_button = QPushButton("실행")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.open_folder_button = QPushButton("폴더 열기")

        self.run_button.clicked.connect(self._on_run_clicked)

        form_layout = QFormLayout()
        address_row = QHBoxLayout()
        address_row.addWidget(self.address_input)
        address_row.addWidget(self.search_button)
        form_layout.addRow("지번:", address_row)
        form_layout.addRow("좌표계:", self.coord_system_combo)
        form_layout.addRow(self.include_topo_checkbox)
        form_layout.addRow(self.include_ortho_checkbox)
        form_layout.addRow("버퍼 거리(m):", self.buffer_input)
        form_layout.addRow("도곽 형태:", self.border_shape_combo)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.run_button)
        layout.addWidget(QLabel("진행 로그:"))
        layout.addWidget(self.log_view)
        layout.addWidget(self.open_folder_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def collect_export_options(self) -> ExportOptions:
        return ExportOptions(
            coord_system=self.coord_system_combo.currentData(),
            buffer_meters=float(self.buffer_input.text()),
            border_shape=self.border_shape_combo.currentData(),
            include_topo=self.include_topo_checkbox.isChecked(),
            include_ortho=self.include_ortho_checkbox.isChecked(),
        )

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _on_run_clicked(self) -> None:
        address = self.address_input.text().strip()
        if not address:
            QMessageBox.warning(self, "입력 필요", "지번을 입력해 주세요")
            return

        selected_dir = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if not selected_dir:
            return
        self.output_dir = selected_dir

        try:
            options = self.collect_export_options()
            result = run_pipeline(address=address, options=options, output_dir=self.output_dir)
        except Exception as exc:  # noqa: BLE001 - surface any pipeline failure to the user
            self.append_log(f"실패: {exc}")
            QMessageBox.critical(self, "실행 실패", str(exc))
            return

        for message in result.log:
            self.append_log(message)
        self.append_log(f"지적도: {result.cadastral_path}")
        if result.topo_path:
            self.append_log(f"지형도: {result.topo_path}")
        if result.ortho_path:
            self.append_log(f"정사영상: {result.ortho_path}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ui_main_window.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/ui/main_window.py tests/test_ui_main_window.py
git commit -m "feat: add PySide6 main window wired to pipeline"
```

---

### Task 10: 앱 엔트리포인트 (`ui/app.py`)

**Files:**
- Create: `jibeon_cad_tool/src/jibeon_cad_tool/ui/app.py`
- Test: `jibeon_cad_tool/tests/test_app_entrypoint.py`

**Interfaces:**
- Consumes: `MainWindow` from `jibeon_cad_tool.ui.main_window`
- Produces: `main() -> int` — QApplication을 생성하고 `MainWindow`를 표시할 준비를 마친 뒤 종료 코드를 반환 (테스트에서는 `show=False`로 실제 창 표시 없이 구성만 검증)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_app_entrypoint.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from jibeon_cad_tool.ui.app import build_application


def test_build_application_returns_app_and_window():
    app, window = build_application(show=False)
    assert app is not None
    assert window.windowTitle() == "지번 기반 CAD 내보내기"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_app_entrypoint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jibeon_cad_tool.ui.app'`

- [ ] **Step 3: app.py 구현**

```python
# src/jibeon_cad_tool/ui/app.py
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

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_app_entrypoint.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run: `cd jibeon_cad_tool && pytest -v`
Expected: 모든 테스트 PASS (Task 2~10에서 작성한 전체 테스트)

- [ ] **Step 6: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/ui/app.py tests/test_app_entrypoint.py
git commit -m "feat: add application entrypoint wiring QApplication and MainWindow"
```

---

## 후속 작업 (이 플랜 범위 밖)

- 브이월드 API 키 발급 후 `VWorldClient.download_cadastral`의 `NotImplementedError`를 실제 엔드포인트 연동으로 교체
- 국토정보플랫폼 API 키 발급 후 `NgiiClient.download_topo`/`download_ortho`의 `NotImplementedError`를 실제 엔드포인트 연동으로 교체 (정사영상은 GeoTIFF 등 실제 래스터 포맷으로 전환)
- API로 지원되지 않는 다운로드 기능에 대한 Playwright 기반 웹 자동화 폴백 구현
- 다중 지번 일괄 처리 (설계 문서에서 범위 제외로 명시됨)
