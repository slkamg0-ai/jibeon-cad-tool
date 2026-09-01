import pytest
from shapely.geometry import Point, Polygon

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
    # Radius equals buffer_meters directly: this shape also serves as the
    # clip boundary, so it must match the rectangle's half-width, not
    # circumscribe it.
    assert maxx - minx == pytest.approx(2 * 20.0, abs=0.5)


def test_make_border_circle_radius_matches_buffer_meters():
    circle = make_border(0.0, 0.0, 20.0, BorderShape.CIRCLE)
    assert circle.contains(Point(19.0, 0.0))
    assert not circle.contains(Point(21.0, 0.0))
