from shapely.geometry import Polygon

from ..models import CoordSystem, ParcelSearchResult


def mock_search_parcel(address: str) -> ParcelSearchResult:
    return ParcelSearchResult(
        pnu="1111010100100010000",
        address=address,
        x=198000.0,
        y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )


def mock_cadastral_parcels(
    result: ParcelSearchResult,
) -> tuple[list[Polygon], int]:
    cx, cy = result.x, result.y
    target = Polygon([
        (cx - 10, cy - 10), (cx + 10, cy - 10),
        (cx + 10, cy + 10), (cx - 10, cy + 10),
    ])
    neighbor = Polygon([
        (cx + 15, cy - 10), (cx + 35, cy - 10),
        (cx + 35, cy + 10), (cx + 15, cy + 10),
    ])
    return [target, neighbor], 0
