# NGII 다운로드 폴더 사용자 지정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `config/ngii_selectors.json`에 고정돼 있던 `download_folder_label`/`download_watch_dir`를 실행 시점에 UI에서 사용자가 입력해 오버라이드할 수 있게 한다.

**Architecture:** `NgiiWebClient.__init__`에 선택적 오버라이드 매개변수를 추가해 로드된 설정값을 덮어쓰고, `ExportOptions`에 두 필드를 추가해 UI→`pipeline.py`→`NgiiWebClient` 순서로 값을 전달한다. 기존 시그니처는 모두 기본값이 있는 선택적 매개변수로만 확장되므로 하위 호환을 유지한다.

**Tech Stack:** Python 3.11+, PySide6, pytest

## Global Constraints

- 오버라이드 값이 없으면(빈 문자열) 기존처럼 `config/ngii_selectors.json`의 값을 그대로 사용한다 — 하위 호환 유지.
- `pipeline.py`가 이미 명시적으로 주입된 `ngii_client`(테스트에서 주입하는 mock/stub 등)를 받은 경우에는 오버라이드를 적용하지 않는다 — 오직 `run_pipeline`이 기본 `NgiiWebClient()`를 스스로 생성할 때만 오버라이드를 반영한다.
- 국토정보플랫폼 전송관리 팝업은 이미 사이트에 등록된 폴더 목록에서만 고를 수 있다(임의 경로 직접 입력 불가) — 이 앱은 사이트에 새 폴더를 등록해주지 않으며, 사용자가 미리 사이트에 폴더를 등록해두고 그 폴더명을 입력해야 한다는 점을 UI 라벨이나 placeholder로 안내한다.

---

## 파일 구조 (기존 구조에서 변경되는 부분)

```
jibeon_cad_tool/
├── src/jibeon_cad_tool/
│   ├── models.py                      # 수정: ExportOptions에 두 필드 추가
│   ├── pipeline.py                    # 수정: 기본 NgiiWebClient 생성 시 오버라이드 전달
│   ├── clients/
│   │   └── ngii_web_client.py         # 수정: __init__에 오버라이드 매개변수 추가
│   └── ui/
│       └── main_window.py             # 수정: 저장 폴더명/로컬 감시 경로 입력란 추가
└── tests/
    ├── test_models.py                 # 수정
    ├── test_ngii_web_client.py        # 수정
    ├── test_pipeline.py               # 수정
    └── test_ui_main_window.py         # 수정
```

---

### Task 1: 백엔드 — `ExportOptions`/`NgiiWebClient`/`pipeline.py` 오버라이드 배선

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/models.py`
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/pipeline.py`
- Modify: `jibeon_cad_tool/tests/test_models.py`
- Modify: `jibeon_cad_tool/tests/test_ngii_web_client.py`
- Modify: `jibeon_cad_tool/tests/test_pipeline.py`

**Interfaces:**
- `ExportOptions`에 `download_folder_label: str = ""`, `download_watch_dir: str = ""` 필드 추가 (마지막 필드로, 기존 필드 순서/기본값 불변)
- `NgiiWebClient.__init__(self, username=None, password=None, use_mock=None, selectors=None, download_folder_label: str | None = None, download_watch_dir: str | None = None)` — 두 매개변수가 주어지고 빈 문자열이 아니면 로드된 `self.selectors`의 해당 필드를 덮어씀
- `run_pipeline`이 `ngii_client`를 스스로 생성할 때 `options.download_folder_label`/`options.download_watch_dir`를 `NgiiWebClient` 생성자에 전달

- [ ] **Step 1: 실패하는 테스트 작성 — `test_models.py`에 추가**

`jibeon_cad_tool/tests/test_models.py` 맨 아래에 추가:

```python
def test_export_options_default_download_folder_fields():
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    assert options.download_folder_label == ""
    assert options.download_watch_dir == ""


def test_export_options_custom_download_folder_fields():
    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        download_folder_label="Work",
        download_watch_dir="G:\\내 드라이브\\Work",
    )
    assert options.download_folder_label == "Work"
    assert options.download_watch_dir == "G:\\내 드라이브\\Work"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_models.py -v`
Expected: FAIL with `TypeError: ExportOptions.__init__() got an unexpected keyword argument 'download_folder_label'`

- [ ] **Step 3: `models.py` 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/models.py`의 `ExportOptions` 데이터클래스 현재 내용:

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

다음과 같이 교체:

```python
@dataclass
class ExportOptions:
    coord_system: CoordSystem
    buffer_meters: float = 100.0
    border_shape: BorderShape = BorderShape.RECTANGLE
    include_topo: bool = False
    include_ortho: bool = False
    map_scale: MapScale = MapScale.SCALE_5000
    download_folder_label: str = ""
    download_watch_dir: str = ""
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_models.py -v`
Expected: PASS (전체)

- [ ] **Step 5: `NgiiWebClient` 오버라이드 실패하는 테스트 작성 — `test_ngii_web_client.py`에 추가**

```python
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
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v -k override`
Expected: FAIL with `TypeError: NgiiWebClient.__init__() got an unexpected keyword argument 'download_folder_label'`

- [ ] **Step 7: `ngii_web_client.py`의 `__init__` 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/clients/ngii_web_client.py`의 현재 `__init__`:

```python
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
```

다음과 같이 교체:

```python
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
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ngii_web_client.py -v`
Expected: PASS (전체)

- [ ] **Step 9: `pipeline.py` 배선 실패하는 테스트 작성 — `test_pipeline.py`에 추가**

```python
def test_run_pipeline_passes_download_folder_overrides_to_default_ngii_client(tmp_path, monkeypatch):
    captured_kwargs = {}

    class _CapturingNgiiWebClient:
        def __init__(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            self.use_mock = True

        def download_topo(self, result, coord_system, map_scale, sheet_features, output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("TOPO stub\n")
            from jibeon_cad_tool.clients.ngii_client import RasterDownloadResult
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

        def download_ortho(self, result, coord_system, map_scale, sheet_features, output_path, **_kwargs):
            return None

    monkeypatch.setattr("jibeon_cad_tool.pipeline.NgiiWebClient", _CapturingNgiiWebClient)

    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        include_topo=True,
        download_folder_label="Work",
        download_watch_dir="/custom/watch",
    )
    run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
    )

    assert captured_kwargs.get("download_folder_label") == "Work"
    assert captured_kwargs.get("download_watch_dir") == "/custom/watch"


def test_run_pipeline_does_not_override_explicitly_injected_ngii_client(tmp_path):
    class _StubNgiiClient:
        def __init__(self):
            self.use_mock = True
            self.received_init_kwargs = None

        def download_topo(self, result, coord_system, map_scale, sheet_features, output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("TOPO stub\n")
            from jibeon_cad_tool.clients.ngii_client import RasterDownloadResult
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

    stub = _StubNgiiClient()
    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        include_topo=True,
        download_folder_label="Work",
        download_watch_dir="/custom/watch",
    )
    run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=stub,
    )

    assert stub.received_init_kwargs is None
```

`tests/test_pipeline.py` 상단 import에 `from jibeon_cad_tool.pipeline import run_pipeline`가 이미 있으므로 그대로 두고, 새로 `NgiiWebClient`를 monkeypatch하므로 별도 import는 필요 없다.

- [ ] **Step 10: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_pipeline.py -v -k download_folder`
Expected: FAIL — `captured_kwargs`가 비어있거나 `download_folder_label`/`download_watch_dir` 키가 없어 `assert` 실패 (아직 `pipeline.py`가 이 값들을 전달하지 않으므로)

- [ ] **Step 11: `pipeline.py` 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/pipeline.py`의 현재 내용:

```python
    vworld_client = vworld_client or VWorldClient()
    ngii_client = ngii_client or NgiiWebClient()
```

다음과 같이 교체:

```python
    vworld_client = vworld_client or VWorldClient()
    if ngii_client is None:
        ngii_kwargs = {}
        if options.download_folder_label:
            ngii_kwargs["download_folder_label"] = options.download_folder_label
        if options.download_watch_dir:
            ngii_kwargs["download_watch_dir"] = options.download_watch_dir
        ngii_client = NgiiWebClient(**ngii_kwargs)
```

- [ ] **Step 12: 테스트 통과 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_pipeline.py -v`
Expected: PASS (전체)

- [ ] **Step 13: 전체 스위트 회귀 확인**

Run: `cd jibeon_cad_tool && pytest -v`
Expected: 전체 PASS (0 실패)

- [ ] **Step 14: Commit**

```bash
cd jibeon_cad_tool
git add src/jibeon_cad_tool/models.py src/jibeon_cad_tool/clients/ngii_web_client.py src/jibeon_cad_tool/pipeline.py tests/test_models.py tests/test_ngii_web_client.py tests/test_pipeline.py
git commit -m "feat: allow NGII download folder label/watch dir to be overridden per pipeline run"
```

---

### Task 2: UI — 저장 폴더명/로컬 감시 경로 입력란 추가

**Files:**
- Modify: `jibeon_cad_tool/src/jibeon_cad_tool/ui/main_window.py`
- Modify: `jibeon_cad_tool/tests/test_ui_main_window.py`

**Interfaces:**
- `MainWindow.download_folder_label_input` (QLineEdit), `MainWindow.download_watch_dir_input` (QLineEdit) 추가
- `collect_export_options()`가 두 입력란의 텍스트를 `ExportOptions.download_folder_label`/`download_watch_dir`에 반영

- [ ] **Step 1: 실패하는 테스트 작성 — `test_ui_main_window.py`에 추가**

```python
def test_main_window_has_download_folder_inputs(qapp):
    window = MainWindow()
    assert window.download_folder_label_input is not None
    assert window.download_watch_dir_input is not None


def test_collect_export_options_reflects_download_folder_inputs(qapp):
    window = MainWindow()
    window.download_folder_label_input.setText("Work")
    window.download_watch_dir_input.setText("G:\\내 드라이브\\Work")

    options = window.collect_export_options()

    assert options.download_folder_label == "Work"
    assert options.download_watch_dir == "G:\\내 드라이브\\Work"


def test_collect_export_options_download_folder_defaults_empty(qapp):
    window = MainWindow()

    options = window.collect_export_options()

    assert options.download_folder_label == ""
    assert options.download_watch_dir == ""
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd jibeon_cad_tool && pytest tests/test_ui_main_window.py -v`
Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute 'download_folder_label_input'`

- [ ] **Step 3: `main_window.py` 수정**

`jibeon_cad_tool/src/jibeon_cad_tool/ui/main_window.py`의 `__init__` 안, `self.map_scale_combo` 생성 코드 뒤(현재 아래 코드 뒤)에:

```python
        self.map_scale_combo = QComboBox()
        for map_scale in MapScale:
            self.map_scale_combo.addItem(MAP_SCALE_LABELS[map_scale], map_scale)
```

다음 두 줄을 추가:

```python
        self.download_folder_label_input = QLineEdit()
        self.download_folder_label_input.setPlaceholderText("국토정보플랫폼에 미리 등록해둔 폴더명 (예: Work)")
        self.download_watch_dir_input = QLineEdit()
        self.download_watch_dir_input.setPlaceholderText("그 폴더의 로컬 경로 (예: G:\\내 드라이브\\Work)")
```

`form_layout.addRow("축척:", self.map_scale_combo)` 바로 뒤에 다음 두 줄을 추가:

```python
        form_layout.addRow("NGII 저장 폴더명:", self.download_folder_label_input)
        form_layout.addRow("NGII 로컬 감시 경로:", self.download_watch_dir_input)
```

`collect_export_options` 메서드 현재 내용:

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

다음과 같이 교체:

```python
    def collect_export_options(self) -> ExportOptions:
        return ExportOptions(
            coord_system=self.coord_system_combo.currentData(),
            buffer_meters=float(self.buffer_input.text()),
            border_shape=self.border_shape_combo.currentData(),
            include_topo=self.include_topo_checkbox.isChecked(),
            include_ortho=self.include_ortho_checkbox.isChecked(),
            map_scale=self.map_scale_combo.currentData(),
            download_folder_label=self.download_folder_label_input.text().strip(),
            download_watch_dir=self.download_watch_dir_input.text().strip(),
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
git commit -m "feat: add UI inputs for NGII download folder label and local watch directory"
```

---

## 후속 작업 (이 플랜 범위 밖)

- 저장 폴더명 입력값이 실제로 사이트에 등록된 폴더와 일치하지 않을 경우의 사용자 안내(예: 명확한 에러 메시지)는 다루지 않음 — `_submit_transfer`가 `get_by_text(label)`로 못 찾으면 Playwright 자체 타임아웃 예외가 그대로 올라감
- 입력란에 최근 사용한 값을 기억해두는 기능(예: QSettings)은 이번 범위 밖
