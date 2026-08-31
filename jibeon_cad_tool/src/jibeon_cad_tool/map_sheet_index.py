import json
import sqlite3
from pathlib import Path

from pyproj import Transformer
from shapely import wkb as shapely_wkb
from shapely.geometry import Point, shape

from .models import CoordSystem, MapScale


def load_index(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]


def find_map_sheet(x: float, y: float, scale: MapScale, features: list[dict]) -> str:
    point = Point(x, y)
    for feature in features:
        if feature["properties"].get("scale") != scale.value:
            continue
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            return feature["properties"]["sheet_no"]
    raise ValueError(f"좌표 ({x}, {y})를 포함하는 {scale.value} 도엽을 찾을 수 없습니다")


# 국토지리정보원이 공식 배포하는 전국 수치지형도 인덱스(GeoPackage, EPSG:5179)를 그대로 사용한다.
# https://www.ngii.go.kr/kor/contents/view.do?sq=1262&board_code=contents_data (INDEX.zip)
# 1:1,000 인덱스는 약 44만 폴리곤이라 전체를 메모리에 올리지 않고, GeoPackage에 내장된
# R-Tree 공간 인덱스(rtree_<table>_geom)로 후보를 좁힌 뒤 정확히 포함하는 도엽만 찾는다.
GPKG_TABLE_NAMES = {
    MapScale.SCALE_5000: "TN_MAPINDX_5K",
    MapScale.SCALE_1000: "TN_MAPINDX_1000",
}
GPKG_CRS = "EPSG:5179"


def _parse_gpkg_geometry(blob: bytes):
    # GeoPackage 이진 지오메트리 형식: "GP" 매직바이트(2) + 버전(1) + 플래그(1)
    # + [SRS ID(4)] + [envelope] + WKB. envelope 크기는 플래그 바이트의 비트 1~3으로 결정된다.
    flags = blob[3]
    envelope_code = (flags >> 1) & 0x07
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    header_len = 8 + envelope_sizes.get(envelope_code, 0)
    return shapely_wkb.loads(blob[header_len:])


def find_map_sheet_in_gpkg(
    x: float,
    y: float,
    scale: MapScale,
    index_dir: Path,
    src_crs: CoordSystem = CoordSystem.GRS80_MID,
) -> str:
    table = GPKG_TABLE_NAMES[scale]
    gpkg_path = Path(index_dir) / f"{table}.gpkg"
    transformer = Transformer.from_crs(src_crs.value, GPKG_CRS, always_xy=True)
    gx, gy = transformer.transform(x, y)

    conn = sqlite3.connect(str(gpkg_path))
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id FROM rtree_{table}_geom WHERE minx <= ? AND maxx >= ? AND miny <= ? AND maxy >= ?",
            (gx, gx, gy, gy),
        )
        candidate_ids = [row[0] for row in cur.fetchall()]
        if not candidate_ids:
            raise ValueError(f"좌표 ({x}, {y})를 포함하는 {scale.value} 도엽을 찾을 수 없습니다")

        point = Point(gx, gy)
        placeholders = ",".join("?" * len(candidate_ids))
        cur.execute(f"SELECT geom, MAPIDCD_NO FROM {table} WHERE fid IN ({placeholders})", candidate_ids)
        for blob, sheet_no in cur.fetchall():
            polygon = _parse_gpkg_geometry(blob)
            if polygon.contains(point):
                return sheet_no
        raise ValueError(f"좌표 ({x}, {y})를 포함하는 {scale.value} 도엽을 찾을 수 없습니다")
    finally:
        conn.close()
