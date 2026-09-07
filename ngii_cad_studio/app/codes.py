import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

CODES_FILE = Path(__file__).parent / "standard_codes.json"

_DATA: Dict[str, Any] = {}
_TREE: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
_BY_CODE: Dict[str, Dict[str, Any]] = {}

def _load_codes():
    global _DATA, _TREE, _BY_CODE
    if CODES_FILE.exists():
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            _DATA = json.load(f)
            _TREE = _DATA.get("tree", {})
            _BY_CODE = _DATA.get("by_code", {})

_load_codes()

# Architectural Drafting Palette (Grayscale baseline with distinct contrast & lineweights)
# ACI Colors:
# 8: Dark Gray (84,84,84) - Roads, subtle boundaries, spot elevations
# 9: Light Gray (168,168,168) - Major contours, cadastral labels
# 250: Faint Gray (33%) - Minor contours, background topography
# 251: Slate Gray (46%) - Existing buildings, water
# 252: Medium Gray (60%) - Cadastral boundaries, curb lines
# 253: Light Slate (73%) - Retaining walls, secondary lines
# 7: White/Black - Title block & crisp annotations
# 1: Red - Primary site boundary (HIGHLIGHT / 대지경계선)
CATEGORY_DEFAULTS = {
    "교통": {"color": "#64748B", "fill_color": "#94A3B8", "dxf_color": 8, "weight": 2.0},
    "건물": {"color": "#475569", "fill_color": "#334155", "dxf_color": 251, "weight": 2.2, "fill_opacity": 0.35},
    "시설": {"color": "#64748B", "fill_color": "#CBD5E1", "dxf_color": 253, "weight": 1.5},
    "식생": {"color": "#475569", "fill_color": "#94A3B8", "dxf_color": 8, "weight": 1.2, "fill_opacity": 0.2},
    "수계": {"color": "#64748B", "fill_color": "#94A3B8", "dxf_color": 8, "weight": 1.8, "fill_opacity": 0.3},
    "지형": {"color": "#475569", "fill_color": "#94A3B8", "dxf_color": 8, "weight": 1.2},
    "경계": {"color": "#64748B", "fill_color": "#CBD5E1", "dxf_color": 8, "weight": 1.5, "dash_array": "5,5"},
    "주기": {"color": "#94A3B8", "fill_color": "#E2E8F0", "dxf_color": 9, "weight": 1.0},
    "기타": {"color": "#64748B", "fill_color": "#CBD5E1", "dxf_color": 8, "weight": 1.5}
}

# Special styling for specific features
SPECIFIC_STYLES = {
    # Contours (주곡선 vs 계곡선 분별성)
    "F0017111": {"color": "#475569", "dxf_color": 250, "weight": 1.0, "name_suffix": "(주곡선)"},
    "F0017112": {"color": "#475569", "dxf_color": 250, "weight": 0.8, "name_suffix": "(간곡선)"},
    "F0017113": {"color": "#94A3B8", "dxf_color": 9, "weight": 2.0, "name_suffix": "(계곡선)"},
    "F0017114": {"color": "#334155", "dxf_color": 250, "weight": 0.6, "name_suffix": "(조곡선)"},
    # Spot elevations
    "F0027211": {"color": "#64748B", "dxf_color": 8, "weight": 1.2, "point_radius": 2.5},
    "F0027217": {"color": "#64748B", "dxf_color": 8, "weight": 1.2, "point_radius": 2.5},
    # Existing Buildings
    "B0010000": {"color": "#475569", "fill_color": "#334155", "dxf_color": 251, "weight": 2.2, "fill_opacity": 0.35},
    # Roads
    "A0010000": {"color": "#64748B", "fill_color": "#475569", "dxf_color": 8, "weight": 2.0},
    "A0020000": {"color": "#64748B", "dxf_color": 8, "weight": 1.5, "dash_array": "8,4"},
    # Water
    "E0010001": {"color": "#64748B", "fill_color": "#475569", "dxf_color": 8, "weight": 1.8, "fill_opacity": 0.3},
    "C0010000": {"color": "#64748B", "fill_color": "#475569", "dxf_color": 8, "weight": 1.8, "fill_opacity": 0.3},
}

def extract_code_from_string(text: str) -> Optional[str]:
    """Extract standard code (e.g. A0010000, F0017111, B001) from filename or layer name."""
    clean = Path(text).stem
    
    # 1. Look for full 8-char pattern: 1 Letter + 7 Digits (e.g. A0010000, F0017111)
    m8 = re.search(r'([A-H]\d{7})', clean, re.IGNORECASE)
    if m8:
        return m8.group(1).upper()
        
    # 2. Look for 4-char pattern: 1 Letter + 3 Digits (e.g. A001, B001, F001)
    m4 = re.search(r'([A-H]\d{3})', clean, re.IGNORECASE)
    if m4:
        return m4.group(1).upper()
        
    return None

def lookup_code(raw_name: str) -> Dict[str, Any]:
    """Lookup standard classification for a given filename or layer name."""
    code = extract_code_from_string(raw_name)
    
    if code and code in _BY_CODE:
        item = _BY_CODE[code].copy()
        major = item.get("major", "기타")
        style = CATEGORY_DEFAULTS.get(major, CATEGORY_DEFAULTS["기타"]).copy()
        if code in SPECIFIC_STYLES:
            style.update(SPECIFIC_STYLES[code])
        item["style"] = style
        return item
        
    # If 4-char code e.g. A001, look for prefix in _BY_CODE
    if code and len(code) == 4:
        # find first matching
        for k, v in _BY_CODE.items():
            if k.startswith(code):
                item = {
                    "code": code,
                    "major": v.get("major", "기타"),
                    "mid": v.get("mid", "기타"),
                    "minor": f"{v.get('mid')} (대표코드 {code})",
                    "geom": v.get("geom", ""),
                    "note": None
                }
                major = item["major"]
                style = CATEGORY_DEFAULTS.get(major, CATEGORY_DEFAULTS["기타"]).copy()
                item["style"] = style
                return item
                
    # Fallback if no code matched
    major = "기타"
    letter = raw_name[0].upper() if raw_name else ""
    major_map = {
        "A": "교통", "B": "건물", "C": "시설", "D": "식생",
        "E": "수계", "F": "지형", "G": "경계", "H": "주기"
    }
    if letter in major_map:
        major = major_map[letter]
        
    style = CATEGORY_DEFAULTS.get(major, CATEGORY_DEFAULTS["기타"]).copy()
    return {
        "code": code or raw_name,
        "major": major,
        "mid": "기타",
        "minor": raw_name,
        "geom": "",
        "style": style
    }

def get_taxonomy_tree() -> Dict[str, Any]:
    """Return full 3-tier taxonomy tree (대분류 > 중분류 > 소분류)."""
    return _TREE

def get_presets() -> Dict[str, Any]:
    """Return ready-to-use practical application presets."""
    return {
        "site_analysis": {
            "id": "site_analysis",
            "name": "건축 / 대지분석 맵",
            "icon": "building",
            "description": "건물 외곽선, 도로경계, 보도, 하천, 행정경계를 추출하여 대지 분석 및 마스터플랜에 활용",
            "rule": {
                "majors": ["건물"],
                "mids": ["도로경계", "인도(보도)", "하천경계", "행정경계"],
                "codes": ["A0010000", "A0033324", "B0010000", "E0010001", "G0010000"]
            }
        },
        "terrain_3d": {
            "id": "terrain_3d",
            "name": "토목 / 3D 지형 모델링",
            "icon": "mountain",
            "description": "등고선(주곡선/계곡선/간곡선), 표고점, 옹벽, 사면을 3D Z고도값과 함께 추출하여 지형 모델(TIN/Mesh) 제작",
            "rule": {
                "majors": ["지형"],
                "mids": ["등고선", "표고점", "옹벽", "성/절토"],
                "codes": ["F0010000", "F0017111", "F0017112", "F0017113", "F0020000", "F0027217", "F0040000"]
            }
        },
        "road_network": {
            "id": "road_network",
            "name": "도로교통망 분석",
            "icon": "car",
            "description": "도로경계, 도로중심선, 교량, 터널, 교차로, 철도망 중심 추출",
            "rule": {
                "majors": [],
                "mids": ["도로경계", "도로중심선", "인도(보도)", "교량", "터널", "교차로", "철도", "철도중심선"],
                "codes": ["A0010000", "A0020000", "A0033324", "A0070000", "A0110020", "A0150000"]
            }
        },
        "hydrology": {
            "id": "hydrology",
            "name": "수계 / 친수공간 현황",
            "icon": "water",
            "description": "하천, 하천중심선, 호수/저수지, 용수로, 해안선 및 댐/제방 시설 추출",
            "rule": {
                "majors": ["수계"],
                "mids": ["하천경계", "하천중심선", "호수/저수지", "해안선", "댐", "제방"],
                "codes": ["E0010001", "E0020000", "E0052114", "E0080000", "C0010000", "C0050000"]
            }
        },
        "nature": {
            "id": "nature",
            "name": "자연환경 / 녹지 현황",
            "icon": "tree",
            "description": "경지계, 지류계(수목), 등고선, 하천을 결합한 자연환경 분석도",
            "rule": {
                "majors": ["식생"],
                "mids": ["경지계", "지류계", "독립수", "등고선", "하천경계"],
                "codes": ["D0010000", "D0020000", "D0030000", "F0017111", "E0010001"]
            }
        }
    }
