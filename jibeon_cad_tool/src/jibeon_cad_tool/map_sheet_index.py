import json
from pathlib import Path

from shapely.geometry import Point, shape

from .models import MapScale


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
