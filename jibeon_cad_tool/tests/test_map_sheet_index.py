from pathlib import Path

import pytest

from jibeon_cad_tool.models import CoordSystem, MapScale
from jibeon_cad_tool.map_sheet_index import find_map_sheet, find_map_sheet_in_gpkg, load_index

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "map_sheet_index_fixture.geojson"
REAL_INDEX_DIR = Path(__file__).parent.parent / "data"


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


def test_find_map_sheet_in_gpkg_returns_sheet_no_for_real_known_address():
    # 경기 화성시 만세구 송산면 사강리 671 — 실 계정으로 국토정보플랫폼 UI에서
    # 검색해 도엽번호 "37615020"(1:5,000, 대부020)이 나오는 것을 직접 확인한 좌표
    sheet_no = find_map_sheet_in_gpkg(
        176453.942652644, 512757.609257195, MapScale.SCALE_5000, REAL_INDEX_DIR
    )
    assert sheet_no == "37615020"


def test_find_map_sheet_in_gpkg_works_for_1000_scale_too():
    sheet_no = find_map_sheet_in_gpkg(
        176453.942652644, 512757.609257195, MapScale.SCALE_1000, REAL_INDEX_DIR
    )
    assert sheet_no


def test_find_map_sheet_in_gpkg_raises_for_coordinates_outside_korea():
    with pytest.raises(ValueError):
        find_map_sheet_in_gpkg(0.0, 0.0, MapScale.SCALE_5000, REAL_INDEX_DIR)


def test_find_map_sheet_in_gpkg_respects_src_crs_parameter():
    sheet_no_default = find_map_sheet_in_gpkg(
        176453.942652644, 512757.609257195, MapScale.SCALE_5000, REAL_INDEX_DIR, src_crs=CoordSystem.GRS80_MID
    )
    assert sheet_no_default == "37615020"
