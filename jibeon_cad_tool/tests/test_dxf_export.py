import ezdxf
from shapely.geometry import Polygon

from jibeon_cad_tool.models import BorderShape
from jibeon_cad_tool.geometry import make_buffer_box
from jibeon_cad_tool.dxf_export import build_cadastral_dxf


def test_build_cadastral_dxf_creates_layers_and_highlight(tmp_path):
    target = Polygon([(90, 90), (110, 90), (110, 110), (90, 110)])
    neighbor = Polygon([(200, 200), (220, 200), (220, 220), (200, 220)])
    clip_box = make_buffer_box(100.0, 100.0, 50.0)
    output_path = str(tmp_path / "cadastral.dxf")

    build_cadastral_dxf(
        parcels=[target, neighbor],
        target_index=0,
        clip_box=clip_box,
        border_shape=BorderShape.RECTANGLE,
        center_x=100.0,
        center_y=100.0,
        buffer_meters=50.0,
        output_path=output_path,
    )

    doc = ezdxf.readfile(output_path)
    msp = doc.modelspace()
    layer_names = {layer.dxf.name for layer in doc.layers}
    assert {"CADASTRAL", "HIGHLIGHT", "BORDER"}.issubset(layer_names)

    highlight_entities = list(msp.query('LWPOLYLINE[layer=="HIGHLIGHT"]'))
    assert len(highlight_entities) == 1

    border_entities = list(msp.query('LWPOLYLINE[layer=="BORDER"]'))
    assert len(border_entities) == 1

    cadastral_entities = list(msp.query('LWPOLYLINE[layer=="CADASTRAL"]'))
    assert len(cadastral_entities) == 0
