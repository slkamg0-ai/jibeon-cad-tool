# 실 API 연동 — 브이월드/국토정보플랫폼 설계 문서

## 배경 및 목적

[2026-08-30-jibeon-cad-export-design.md](2026-08-30-jibeon-cad-export-design.md)에서 만든 `jibeon_cad_tool`은 지금까지 브이월드/국토정보플랫폼 API를 목업 모드로만 동작해왔다. 사용자가 브이월드 오픈API 인증키, 국토정보플랫폼 오픈API 인증키, 국토정보플랫폼 로그인 계정(아이디/비밀번호)을 모두 발급·보유하게 되어, 이 문서는 목업 모드를 실제 데이터 연동으로 교체하는 작업을 설계한다.

## 범위

- `VWorldClient`의 `search_parcel`/`download_cadastral`을 실 API 호출로 교체
- `NgiiClient`의 `download_topo`/`download_ortho`를 실제 파일 다운로드로 교체 — 단, 국토정보플랫폼은 API 키 기반이 아니라 **로그인 세션 기반 웹 자동화**로 동작함이 실제 사이트 조사로 확인되었으므로, 이를 반영한 새로운 클라이언트 구조를 설계한다
- 좌표→도엽번호 변환을 위한 로컬 도엽 인덱스 조회 기능 추가
- 자격증명(.env) 관리 추가

다중 지번 일괄 처리, Playwright 자동화의 사이트 구조 변경 대응(자체 모니터링/알림)은 이 문서의 범위 밖이다.

## 브이월드(VWorld) 실 연동

### 검색 (search_parcel)

기존 `_parse_search_response`는 이미 `service=search&request=search&type=address&category=parcel` 파라미터로 브이월드 검색 API를 호출하도록 스캐폴딩되어 있다. 실 연동 시 다음을 반영한다:

- 요청 파라미터에 `crs=EPSG:5186`을 명시적으로 추가하여, 실 API 응답 좌표가 항상 GRS80 중부원점 기준으로 오도록 고정한다 (기존에는 응답 좌표계를 코드에서 `CoordSystem.GRS80_MID`로 하드코딩만 하고 요청 파라미터에는 반영하지 않아, 실제로는 다른 좌표계로 응답이 올 수 있는 결함이 있었다 — 이번에 함께 수정한다)
- 응답에 `items`가 없으면 기존과 동일하게 `ValueError`

### 지적도 다운로드 (download_cadastral)

브이월드 지적도는 CAD 원본 파일이 아니라 **Data API(WFS GetFeature)**를 통해 GeoJSON 형태의 필지 폴리곤으로 제공된다. 대상 레이어는 `LP_PA_CBND_BUBUN`(지적도_지적)이다.

- 요청: `https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BUBUN&key={API_KEY}&geomFilter=POINT({x} {y})&format=json&crs=EPSG:5186&size=100`로 검색 결과 좌표 주변의 필지들을 조회
- 응답의 GeoJSON `features[].geometry.coordinates`를 shapely `Polygon`으로 변환
- 응답의 `features[].properties`에 포함된 PNU(고유번호) 필드와 검색 결과의 `pnu`를 비교하여 대상 필지의 인덱스(target_index)를 결정한다. 일치하는 필지가 없으면 검색 좌표를 포함(`contains`)하는 첫 폴리곤을 대상으로 삼는다
- 반환 형식은 기존 목업과 동일하게 `tuple[list[Polygon], int]`을 유지하여 `pipeline.py`가 수정 없이 그대로 동작하게 한다

## 국토정보플랫폼(NGII) 실 연동

> **개정 이력**: 이 섹션은 최초 작성 후 사용자가 `playwright codegen`으로 실제 로그인·다운로드 흐름을 캡처한 결과를 반영해 전면 재작성되었다. 최초 가정(시도/시군구/축척/도엽번호를 텍스트로 검색하는 카탈로그 페이지, 장바구니→신청→다운로드 링크 클릭)은 **실제 사이트와 다르다는 것이 확인**되어 폐기되었다. 아래가 실제 캡처 기반의 현재 설계다.

### 왜 API 키 방식이 아닌가

`map.ngii.go.kr` 실사이트 조사 결과, 오픈API(인증키 발급 대상)는 배경지도(WMTS)·검색(POI/지오코딩)만 제공하며, 수치지형도/정사영상은 로그인 세션 기반의 대화형 웹 다운로드 흐름으로 제공된다.

따라서 `NgiiClient`는 API 키가 아니라 **Playwright 기반 웹 자동화**로 재구현한다. `NGII_API_KEY`는 이번 범위에서는 사용하지 않으며(향후 오픈API 기반 배경지도/POI 기능이 추가될 때 사용), `NGII_USERNAME`/`NGII_PASSWORD`가 이 클라이언트의 실제 인증 수단이 된다.

### 실제 캡처된 흐름

`playwright codegen https://map.ngii.go.kr`로 사용자가 직접 캡처한 결과, 실제 흐름은 다음과 같다:

1. **로그인**: 홈에서 "로그인" 링크 클릭 → "아이디 로그인" 링크 클릭 시 **팝업 창**이 열림 (`page.expect_popup()`) → 팝업 안에서 placeholder 기반 아이디/비밀번호 입력창(`get_by_placeholder(...)`)에 값 입력 → "회원 들어가기" 버튼 클릭 → 팝업 닫힘
2. **위치 검색**: 메인 메뉴 "국토정보맵" → "통합지도검색" → 검색창(`#totalSearchKeyword`)에 **주소**(브이월드 검색 결과의 `address`) 입력 후 Enter → "간편지도 검색" 클릭 → "인덱스" 토글 클릭 → 축척 버튼(예: ":5,000") 클릭
3. **지도 위치 클릭**: 주소로 검색하면 지도가 항상 검색된 위치로 이동하며 핀/중앙이 고정적으로 표시됨(사용자 확인) → 지도 컨테이너 요소의 bounding box 중심 좌표를 계산해 그 지점을 2회 클릭 (캡처에서는 `.ol-unselectable > div:nth-child(3)`이라는 고정 픽셀 셀렉터를 썼지만, 이는 그 검색 세션에만 우연히 맞는 값이라 실제 구현에서는 지도 컨테이너의 bounding box 중심을 동적으로 계산해서 클릭한다)
4. "검색" 버튼 클릭 → 카테고리 목록에서 "수치지도" → "수치지형도(DXF파일)" 등 하위 카테고리 클릭 (목록 옆의 개수 표시 `(26)`, `(9)`는 검색마다 달라지므로 정확한 라벨 전체가 아니라 부분 텍스트로 매칭)
5. 결과 목록의 체크박스(`<i>` 아이콘)들을 순서대로 클릭해 원하는 항목(제작연도 등)을 선택 — **이 단계는 검색 결과 개수·순서에 의존하는 위치 기반 클릭이라 다른 지번/축척 조합에서는 깨질 수 있음이 알려진 위험**(사용자가 위험을 인지하고 이번 캡처 그대로 자동화 진행을 승인함)
6. "다운로드" 버튼 클릭 → 모달(`#modalPopup`) → 모달 안 "다운로드" 버튼 클릭 시 **새 팝업(전송관리 창)**이 열림
7. 전송관리 팝업에서 "전체 다운로드" 클릭 → 웹페이지 안에 목록으로 뜨는 저장 폴더(예: 로컬에 마운트된 구글드라이브 경로) 항목을 텍스트로 클릭해 선택 → "전송시작" 클릭 → 팝업 닫힘
8. 실제 파일은 위에서 선택한 로컬 폴더에 저장되므로, 앱이 그 폴더를 감시해 새로 생성된 파일을 찾아 `output_path`로 복사한다

### 캡처된 흐름을 코드로 직접 구현 (범용 인터프리터 대신)

당초 이 문서 초안은 셀렉터를 JSON "단계 목록(macro)" 형태로 저장하고 이를 해석하는 범용 인터프리터를 만드는 방향을 검토했으나, 이미 사용자가 `playwright codegen`으로 실제 동작하는 흐름 전체를 캡처해두었으므로 그 값을 그대로 Python 코드에 직접 반영하는 것이 더 단순하고 테스트하기 쉽다 (이전 태스크들의 `_login`/`_request_sheet` 패턴과 동일). 범용 DSL 인터프리터는 만들지 않는다.

대신 **변하기 쉽거나 환경에 따라 달라지는 값만** `config/ngii_selectors.json`에 남긴다:

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

`map_pin_click_selector`는 이번 캡처에서 그대로 가져온 값이다(사용자가 위험을 인지하고 이번 캡처 그대로 사용을 승인함 — 다른 지번/축척 조합에서 깨질 수 있음을 "미해결" 항목에 기록). `download_folder_label`/`download_watch_dir`는 사용자마다 다른 로컬 환경(구글드라이브 마운트 경로 등)이라 값 자체는 실행 환경에서 채워야 하므로 플레이스홀더로 남긴다. 카테고리 선택(수치지도 → 수치지형도(DXF파일))과 체크박스 클릭 순서, 전송관리 팝업 흐름은 캡처된 그대로 Python 코드(`_select_category_and_items`, `_submit_transfer` 등 메서드)에 직접 구현한다.

### 좌표 → 도엽번호 변환 (용도 변경)

이전 설계는 도엽번호를 텍스트로 검색하는 카탈로그 페이지를 가정해 `map_sheet_index.py`를 만들었으나, 실제 흐름은 주소 검색 + 지도 클릭만 사용하고 도엽번호 텍스트 검색을 전혀 쓰지 않는다. `map_sheet_index.py`(`find_map_sheet`)는 삭제하지 않고 **로그·디버깅용으로만** 유지한다 — 예를 들어 진행 로그에 "도엽 358051 부근 다운로드 시도"처럼 참고 정보를 남기는 용도.

`MapScale` enum(`SCALE_5000`/`SCALE_1000`)은 그대로 유지하며, 이제 실제 흐름의 축척 버튼(`:5,000`/`:1,000`) 클릭에 사용된다.

### 다운로드 자동화 (Playwright) — 개정판

새 클라이언트 `NgiiWebClient` (기존 `NgiiClient`를 대체하되, 목업 모드는 그대로 유지 — `use_mock` 플래그로 목업/실제 웹 자동화를 전환):

1. **로그인** (`_login`): 팝업을 열고 아이디/비밀번호를 입력해 로그인. 팝업의 로그인 폼이 뜨지 않거나 로그인 후에도 로그인 상태가 아니면 즉시 예외 발생, 재시도하지 않음(계정 잠금 방지)
2. **위치 검색 및 선택** (`_search_location`): 주소로 검색 → 간편지도 검색 → 인덱스 토글 → 축척 버튼 클릭 → `map_pin_click_selector`를 `map_click_count`회 클릭
3. **자료 선택 및 신청** (`_select_category_and_items`): 캡처된 순서 그대로 카테고리·체크박스 클릭 (검색 결과 구성이 달라지면 깨질 수 있음을 코드 주석과 로그에 명시)
   - **수치지형도**: 신청 직후 다운로드 흐름을 즉시 진행
   - **정사영상**: 신청 후 처리 상태를 짧은 간격(예: 15초)으로 폴링. 준비되면 다운로드. **10분 타임아웃**을 넘으면 예외 대신 `None`을 반환(전체 파이프라인을 실패시키지 않음)
4. **다운로드** (`_submit_transfer`): "다운로드" → 모달 → 전송관리 팝업에서 "전체 다운로드" → `download_folder_label` 텍스트 클릭 → "전송시작". 이후 `download_watch_dir`를 짧게 폴링해 새로 생성된 파일을 찾아 `output_path`로 복사하고 `RasterDownloadResult(file_path, coord_system)`을 반환

### 목업 모드 유지

`use_mock`(자동 감지: `NGII_USERNAME`/`NGII_PASSWORD` 둘 다 없으면 목업) 로직은 유지한다. 목업 모드에서는 기존과 동일하게 텍스트 스텁 파일을 즉시 작성한다.

### 다운로드 폴더 사용자 지정 (UI 오버라이드)

`config/ngii_selectors.json`의 `download_folder_label`/`download_watch_dir`는 기본값이지만, 사용자마다 로컬 환경(마운트된 드라이브 경로, 사이트에 등록해둔 폴더명)이 다르므로 **UI에서 매 실행마다 오버라이드**할 수 있게 한다.

- `NgiiWebClient.__init__`에 `download_folder_label: str | None = None`, `download_watch_dir: str | None = None` 매개변수를 추가한다. 값이 주어지면(빈 문자열이 아니면) 설정 파일에서 로드한 `self.selectors`의 해당 필드를 덮어쓴다. 값이 없으면 설정 파일 값을 그대로 사용한다(하위 호환).
- `ExportOptions`에 `download_folder_label: str = ""`, `download_watch_dir: str = ""` 필드를 추가한다(기본값은 빈 문자열 — "설정 파일 기본값 사용"을 의미).
- `pipeline.py`가 기본 `NgiiWebClient()`를 생성할 때(사용자가 직접 `ngii_client`를 주입하지 않은 경우) `options.download_folder_label`/`options.download_watch_dir`가 비어있지 않으면 그 값으로 `NgiiWebClient(download_folder_label=..., download_watch_dir=...)`를 생성한다.
- UI(`MainWindow`)에 "저장 폴더명(사이트 등록 이름)"과 "로컬 감시 경로" 두 개의 텍스트 입력란을 추가하고, `collect_export_options()`가 이 값을 `ExportOptions`에 채워 넣는다. **사이트(국토정보플랫폼) 전송관리 팝업은 이미 등록된 폴더 목록에서만 고를 수 있으므로**(임의 경로 직접 입력 불가), 사용자는 미리 사이트에 폴더를 등록해두고 그 폴더명을 여기 입력해야 한다 — 이 앱이 사이트에 새 폴더를 등록해주지는 않는다.

## 자격증명 관리

- 프로젝트 루트에 `.env` 파일 추가 (`.gitignore`에 등록, 커밋되지 않음)
- `VWORLD_API_KEY`, `NGII_API_KEY`, `NGII_USERNAME`, `NGII_PASSWORD`
- `python-dotenv`를 새 의존성으로 추가, 앱 시작 시(`ui/app.py`) `load_dotenv()` 호출
- 기존 클라이언트들의 `os.environ.get(...)` 호출은 그대로 유지 — `load_dotenv()`가 프로세스 환경변수에 값을 채워 넣으므로 클라이언트 코드 변경 불필요
- `.env.example` 파일을 추가하여 필요한 키 이름만 문서화 (실제 값은 없음)

## 에러 처리

- 도엽 인덱스 조회 실패(좌표가 어떤 도엽에도 속하지 않음) → `ValueError`, 파이프라인 중단
- NGII 로그인 실패 → 즉시 예외, 재시도 없음
- 정사영상 승인 대기 타임아웃 → 파이프라인을 실패시키지 않고, "신청 완료·다운로드 대기 중" 상태로 로그에 남기고 `ortho_path`는 `None` 유지
- 브이월드 Data API에서 대상 필지를 찾지 못함(공간 포함 검사도 실패) → `ValueError`

## 테스트 전략

- **VWorld 실 연동**: `requests_mock` 또는 유사 라이브러리로 Data API/검색 API 응답을 목킹한 단위 테스트로 파싱 로직 검증. 실 키를 사용하는 통합 테스트는 소수 케이스로 수동 실행
- **도엽 인덱스 조회**: 로컬 GeoJSON 자산 일부를 고정해 좌표 포함 테스트, 범위 밖 좌표에 대한 `ValueError` 테스트
- **NGII Playwright 자동화**: 실 사이트에 의존하므로 CI에서 자동 실행하지 않고, 로그인 실패/타임아웃 등 예외 경로는 Playwright의 페이지 객체를 모킹해 단위 테스트. 실 다운로드 흐름은 수동 검증
- 기존 파이프라인(`run_pipeline`) 테스트는 그대로 유지(목업 클라이언트 주입) — 실 연동 여부와 무관하게 회귀 확인

## 미해결/후속 검토 사항

- Playwright 자동화는 국토정보플랫폼 사이트 구조 변경에 취약함 — 실패 시 명확한 에러와 함께 수동 확인을 안내하는 것으로 이번 범위에서는 충분히 처리
- **`item_selection_steps`(자료 선택 체크박스 클릭 순서)는 이번 한 번의 캡처 세션에서만 검증됨** — 검색 결과 개수·구성이 달라지는 다른 지번/축척 조합에서는 깨질 수 있다는 위험을 사용자가 인지하고 승인한 상태로 진행. 실 사용 중 실패가 반복되면 이 부분을 좀 더 견고한 방식(예: 텍스트 매칭 기반 동적 탐색)으로 재설계 필요
- `download_folder_label`/`download_watch_dir`는 사용자 로컬 환경(구글드라이브 마운트 경로 등)에 따라 달라지므로 플레이스홀더로 남기고, 실행 전 사용자가 자신의 환경에 맞게 채워야 한다. 나머지 캡처된 값(로그인 흐름, 검색어 셀렉터, 지도 클릭 셀렉터, 카테고리/체크박스 순서)은 이미 확보되었으므로 이번 플랜에서 코드로 직접 반영한다
- 도엽코드 인덱스 데이터셋(공공데이터포털 원본)은 이제 UI 자동화에 쓰이지 않고 로그·디버깅 참고용으로만 남으므로, 실 전국 데이터셋 확보의 우선순위는 낮아짐 — 필요해지면 별도로 진행
- 다운로드된 파일이 실제로 로컬 드라이브(예: 마운트된 구글드라이브 경로)에 나타나기까지 약간의 지연이 있을 수 있어, `download_watch_dir` 폴링에 적절한 타임아웃이 필요함
