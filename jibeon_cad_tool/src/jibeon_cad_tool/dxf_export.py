import ezdxf
from shapely.geometry import Polygon

from .geometry import clip_geometry, make_border
from .models import BorderShape


DEFAULT_LABEL_FONT = "malgun.ttf"
LABEL_TEXT_STYLE = "JIBEON_LABEL"


def build_cadastral_dxf(
    parcels: list[Polygon],
    target_index: int,
    clip_box: Polygon,
    border_shape: BorderShape,
    center_x: float,
    center_y: float,
    buffer_meters: float,
    output_path: str,
    labels: list[str] | None = None,
    label_font: str = DEFAULT_LABEL_FONT,
) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add(name="CADASTRAL", color=7)
    doc.layers.add(name="HIGHLIGHT", color=1)
    doc.layers.add(name="BORDER", color=3)
    doc.layers.add(name="LABEL", color=7)  # ACI 7 = black on the standard white CAD background
    doc.styles.add(LABEL_TEXT_STYLE, font=label_font)

    text_height = 1.0
    for idx, poly in enumerate(parcels):
        clipped = clip_geometry(poly, clip_box)
        if clipped.is_empty:
            continue
        layer = "HIGHLIGHT" if idx == target_index else "CADASTRAL"
        for ring_coords in _polygon_rings(clipped):
            msp.add_lwpolyline(ring_coords, dxfattribs={"layer": layer, "closed": True})

        label = labels[idx] if labels else None
        if label:
            point = clipped.representative_point()
            msp.add_text(
                label,
                dxfattribs={
                    "layer": "LABEL",
                    "height": text_height,
                    "color": 7,
                    "style": LABEL_TEXT_STYLE,
                    "insert": (point.x, point.y),
                },
            ).set_placement((point.x, point.y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

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
