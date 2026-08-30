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

### 왜 API 키 방식이 아닌가

`map.ngii.go.kr` 실사이트 조사 결과, 오픈API(인증키 발급 대상)는 배경지도(WMTS)·검색(POI/지오코딩)만 제공하며, 수치지형도/정사영상은 **민원서비스 > 지도신청 > 카탈로그**에서 시도/시군구/축척/도엽번호로 검색해 장바구니에 담고 신청하는 방식으로 제공된다. 사용자 확인에 따르면 수치지형도는 신청 후 거의 즉시 다운로드 가능하고, 정사영상은 승인 대기가 필요하나 대부분 수 분 이내에 처리된다.

따라서 `NgiiClient`는 API 키가 아니라 **Playwright 기반 웹 자동화**로 재구현한다. `NGII_API_KEY`는 이번 범위에서는 사용하지 않으며(향후 오픈API 기반 배경지도/POI 기능이 추가될 때 사용), `NGII_USERNAME`/`NGII_PASSWORD`가 이 클라이언트의 실제 인증 수단이 된다.

### 좌표 → 도엽번호 변환

`map.ngii.go.kr`의 카탈로그는 주소가 아닌 시도/시군구/축척/도엽번호로 검색한다. 좌표에서 도엽번호를 정확히 찾기 위해:

- 공공데이터포털에서 국토지리정보원이 공개한 **도엽코드 인덱스**(도엽 경계 폴리곤 + 도엽번호, 1:5,000·1:1,000 스케일 포함)를 한 번 내려받아 `jibeon_cad_tool/data/` 아래에 로컬 자산(GeoJSON)으로 저장한다
- 새 모듈 `map_sheet_index.py`가 이 GeoJSON을 로드하고, `find_map_sheet(x: float, y: float, scale: MapScale) -> str`로 좌표를 포함하는 도엽 폴리곤을 공간 조회(shapely `contains`)하여 도엽번호 문자열을 반환한다
- 어떤 도엽 폴리곤에도 속하지 않으면 `ValueError`

`MapScale` enum: `SCALE_5000 = "1:5000"`(기본값), `SCALE_1000 = "1:1000"`(선택)

### 다운로드 자동화 (Playwright)

새 클라이언트 `NgiiWebClient` (기존 `NgiiClient`를 대체하되, 목업 모드는 그대로 유지 — `use_mock` 플래그로 목업/실제 웹 자동화를 전환):

1. **로그인**: `map.ngii.go.kr` 로그인 페이지에 `NGII_USERNAME`/`NGII_PASSWORD`로 로그인. 실패 시 즉시 예외 발생, 재시도하지 않음(계정 잠금 방지)
2. **카탈로그 검색**: `find_map_sheet()`로 얻은 도엽번호와 축척으로 지도자료 카탈로그 검색
3. **신청**: 검색 결과를 장바구니에 담고 신청 제출
   - **수치지형도**: 신청 직후 다운로드 링크가 뜨는지 확인 후 즉시 다운로드
   - **정사영상**: 신청 후 처리 상태를 짧은 간격(예: 15초)으로 폴링. 준비되면 다운로드. **10분 타임아웃**을 넘으면 예외 대신 "신청은 완료, 다운로드는 나중에 확인 필요"를 알리는 별도 결과 상태를 반환(전체 파이프라인을 실패시키지 않음)
4. 다운로드된 파일을 `output_path`에 저장하고 `RasterDownloadResult(file_path, coord_system)`을 반환 (좌표계는 검색에 사용한 `CoordSystem`)

### 목업 모드 유지

`use_mock`(자동 감지: `NGII_USERNAME`/`NGII_PASSWORD` 둘 다 없으면 목업) 로직은 유지한다. 목업 모드에서는 기존과 동일하게 텍스트 스텁 파일을 즉시 작성한다.

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
- 도엽코드 인덱스 데이터셋의 정확한 공공데이터포털 다운로드 URL과 파일 포맷(Shapefile/GeoJSON 여부)은 구현 단계에서 실제 다운로드해 확인 필요
