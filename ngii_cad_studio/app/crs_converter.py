from typing import Tuple, Optional, List
import pyproj

# Standard Korean Coordinate Reference Systems
SUPPORTED_CRS = {
    "EPSG:5186": "Korea 2000 / Central Belt 2010 (수치지형도 표준, GRS80)",
    "EPSG:5179": "Korea 2000 / Unified CS (UTM-K 통합좌표계)",
    "EPSG:5181": "Korea 2000 / Central Belt (카카오맵 타일)",
    "EPSG:5174": "Korean 1985 / Central Belt (구 수치지형도 v1.0, Bessel)",
    "EPSG:4326": "WGS 84 (GPS / GeoJSON / 위경도)",
    "EPSG:3857": "Web Mercator (웹 타일 지도)"
}

_TRANSFORMER_CACHE = {}

def get_transformer(src_crs: str, dst_crs: str) -> pyproj.Transformer:
    key = (src_crs, dst_crs)
    if key not in _TRANSFORMER_CACHE:
        _TRANSFORMER_CACHE[key] = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return _TRANSFORMER_CACHE[key]

def detect_crs_from_bounds(min_x: float, min_y: float, max_x: float, max_y: float) -> str:
    """Heuristically detect CRS from coordinate bounding box values."""
    # 1. WGS84 위경도
    if 124.0 <= min_x <= 132.0 and 32.0 <= min_y <= 39.0:
        return "EPSG:4326"
        
    # 2. UTM-K (EPSG:5179): X is typically 800,000 ~ 1,200,000 and Y is 1,600,000 ~ 2,100,000
    if min_x > 700000 and min_y > 1400000:
        return "EPSG:5179"
        
    # 3. Korea 2000 Central Belt (EPSG:5186) or Bessel (EPSG:5174):
    # Typically X is 150,000 ~ 300,000, Y is 400,000 ~ 650,000
    if 100000 <= min_x <= 400000 and 300000 <= min_y <= 700000:
        return "EPSG:5186"
        
    # Default to 5186 for Korean maps
    return "EPSG:5186"

def detect_crs_from_prj(prj_wkt: str) -> Optional[str]:
    """Detect EPSG from .prj file content."""
    try:
        crs = pyproj.CRS.from_user_input(prj_wkt)
        epsg = crs.to_epsg()
        if epsg:
            return f"EPSG:{epsg}"
    except Exception:
        pass
    return None

def transform_coords(coords: List[Tuple[float, float]], src_crs: str, dst_crs: str) -> List[Tuple[float, float]]:
    if src_crs == dst_crs:
        return coords
    transformer = get_transformer(src_crs, dst_crs)
    transformed = []
    for pt in coords:
        x, y = pt[0], pt[1]
        nx, ny = transformer.transform(x, y)
        if len(pt) > 2:
            transformed.append((nx, ny, pt[2]))
        else:
            transformed.append((nx, ny))
    return transformed
