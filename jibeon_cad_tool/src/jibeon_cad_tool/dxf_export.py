import ezdxf
from shapely.geometry import Polygon

from .geometry import clip_geometry, make_border
from .models import BorderShape


def build_cadastral_dxf(
    parcels: list[Polygon],
    target_index: int,
    clip_box: Polygon,
    border_shape: BorderShape,
    center_x: float,
    center_y: float,
    buffer_meters: float,
    output_path: str,
) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add(name="CADASTRAL", color=7)
    doc.layers.add(name="HIGHLIGHT", color=1)
    doc.layers.add(name="BORDER", color=3)

    for idx, poly in enumerate(parcels):
        clipped = clip_geometry(poly, clip_box)
        if clipped.is_empty:
            continue
        layer = "HIGHLIGHT" if idx == target_index else "CADASTRAL"
        for ring_coords in _polygon_rings(clipped):
            msp.add_lwpolyline(ring_coords, dxfattribs={"layer": layer, "closed": True})

    border = make_border(center_x, center_y, buffer_meters, border_shape)
    for ring_coords in _polygon_rings(border):
        msp.add_lwpolyline(ring_coords, dxfattribs={"layer": "BORDER", "closed": True})

    doc.saveas(output_path)


# Cadastral parcels are assumed to have no interior rings (holes); only exterior boundaries are drawn.
def _polygon_rings(geometry):
    if geometry.geom_type == "Polygon":
        yield list(geometry.exterior.coords)
    elif geometry.geom_type == "MultiPolygon":
        for part in geometry.geoms:
            yield list(part.exterior.coords)
