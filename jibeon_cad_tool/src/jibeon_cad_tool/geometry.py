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
