from pyproj import Transformer

from .models import CoordSystem


def transform_point(x: float, y: float, src: CoordSystem, dst: CoordSystem) -> tuple[float, float]:
    if src == dst:
        return x, y
    transformer = Transformer.from_crs(src.value, dst.value, always_xy=True)
    return transformer.transform(x, y)


def transform_coords(
    coords: list[tuple[float, float]], src: CoordSystem, dst: CoordSystem
) -> list[tuple[float, float]]:
    if src == dst:
        return list(coords)
    transformer = Transformer.from_crs(src.value, dst.value, always_xy=True)
    return [transformer.transform(x, y) for x, y in coords]
