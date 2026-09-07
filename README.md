# 🗺️ Jibeon CAD Tool & NGII Map Studio
> 국토정보플랫폼 3D 수치지형도 & VWorld 실시간 지적도 통합 CAD 도면 추출 플랫폼

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastAPI.tiangolo.com/)

---

## 🌟 프로젝트 개요

본 프로젝트는 건축·토목·도시설계 실무를 위해 **국토교통부 VWorld 실시간 지적도(대지경계선, 지번 주기, 인접 필지)**와 **국토지리정보원 수치지형도(3D 등고선, 현황도로, 기존 건축물, 구거)**를 완벽하게 정합하여 **단 하나의 고품질 CAD 도면(DXF)으로 일괄 추출**하는 통합 솔루션입니다.

---

## 🏗️ 서브 시스템 구성

| 구분 | 1. NGII Map Studio (`ngii_cad_studio/`) [추천] | 2. Jibeon CAD Desktop Tool (`jibeon_cad_tool/`) |
| :--- | :--- | :--- |
| **형태** | **통합 웹 CAD 스튜디오 (웹 브라우저 기반)** | PyQt5 기반 독립형 데스크톱 GUI |
| **핵심 기능** | **수치지형도(DXF/SHP/ZIP) + 실시간 지적도 원클릭 결합** | VWorld 실시간 지적도 단독 추출 |
| **도면 스타일** | **실무 작도용 그레이톤(ACI 8,9,250,251,1,7 ByLayer)** | 기본 컬러 지적선 |
| **도곽 및 클리핑** | **최대 1000m 사각형/원형 버퍼 클리핑 지원** | 100m~300m 사각형/원형 클리핑 |
| **도면 요소** | **방위표(N), 축척 바, 표준 도면 표제란(Title Block) 자동 생성** | 지적선 및 지번 라벨 |
| **스마트 파일명** | **`[주소]_(도엽명)_현황도_YYYYMMDD.dxf` 자동 명명** | 기본 파일명 |
| **공유 모드** | **사내 인트라넷 LAN IP(`0.0.0.0`) 팀원 동시 접속 지원** | 로컬 PC 단독 실행 |

---

## 🚀 빠른 시작 (Web CAD Studio)

### 윈도우 원클릭 실행
프로젝트 루트의 **`start_web_studio.bat`** 파일을 더블 클릭합니다.
- 서버가 백그라운드에서 구동되며 기본 브라우저(`http://localhost:8000`)가 자동으로 열립니다.
- 같은 사무실 Wi-Fi / 사내 네트워크에 연결된 동료들도 콘솔에 표시되는 LAN IP로 동시 접속할 수 있습니다.

### 파이썬 명령어로 실행
```bash
# 1. 의존성 패키지 설치
pip install -r ngii_cad_studio/requirements.txt

# 2. 웹 스튜디오 실행
py run_web_studio.py
```

---

## 📐 설계도면 작도용 그레이톤 레이어 규격 (AutoCAD ACI 표준)

신축 건물, 도로, 조경 계획선 등 새로운 설계선을 얹을 때 바탕 도면이 시각적 피로도를 주지 않도록 차분한 그레이톤을 기본으로 하고, 주요 객체의 분별성을 극대화하였습니다:

| 구분 | 레이어명 | ACI 색상 (CAD) | 선가중치 | 선종류 (Linetype) | 설명 / 실무 목적 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **대지경계** | `HIGHLIGHT` | **Color 1 (Red)** | **0.50 mm (굵은 실선)** | `Continuous` | **신축/설계 대상 필지 대지경계선** |
| **지적선** | `CADASTRAL` | **Color 8 (Dark Gray)** | 0.15 mm (가는 실선) | `Continuous` | 인접 주변 필지 지적선 (부드러운 배경) |
| **지번주기** | `LABEL` | **Color 9 (Light Gray)** | 0.15 mm | `Continuous` | 지번 텍스트 (명확한 번지수 가독성) |
| **도곽선** | `BORDER` | **Color 8 (Dark Gray)** | 0.25 mm | **`DASHED` (가상 파선)** | 분석 범위 / 도곽 경계선 |
| **주곡선** | `F0017113` | **Color 9 (Light Gray)** | 0.25 mm (중간 실선) | `Continuous` | 주요 지형 등고선 |
| **계곡선** | `F0017111` | **Color 250 (Faint Gray)** | 0.13 mm (미세 실선) | `Continuous` | 부드럽게 깔리는 바탕 등고선 |
| **기존건물** | `B001` | **Color 251 (Slate Gray)** | 0.25 mm | `Continuous` | 현황 대지 주변 기존 건축물 |
| **도로중심** | `A002` | **Color 8 (Dark Gray)** | 0.15 mm | **`CENTER` (일점쇄선)** | 도로 중심선 (건축선 후퇴 기준) |
| **표제/방위** | `TITLE_BLOCK` | **Color 7 (White/Black)** | 0.25 mm | `Continuous` | 도면 테두리, 방위표, 축척 바, 표제란 |

> **모든 CAD 엔티티는 `ByLayer (256)`로 설정**되어 있어, AutoCAD 레이어 관리자(`LAYER`)에서 본인의 오피스 표준에 맞추어 색상이나 선가중치를 원클릭으로 일괄 조절할 수 있습니다.
