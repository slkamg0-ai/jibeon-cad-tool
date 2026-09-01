from dataclasses import dataclass
from enum import Enum


class CoordSystem(Enum):
    GRS80_MID = "EPSG:5186"
    GRS80_WEST = "EPSG:5185"
    GRS80_EAST = "EPSG:5187"
    UTMK = "EPSG:5179"
    KATEC = "EPSG:5178"


class BorderShape(Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"


@dataclass
class ParcelSearchResult:
    pnu: str
    address: str
    x: float
    y: float
    coord_system: CoordSystem


@dataclass
class ExportOptions:
    coord_system: CoordSystem
    buffer_meters: float = 100.0
    border_shape: BorderShape = BorderShape.RECTANGLE
    include_topo: bool = False
    include_ortho: bool = False
    label_font: str = "malgun.ttf"
