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
