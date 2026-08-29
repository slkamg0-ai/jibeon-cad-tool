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
