import os

import requests
from shapely.geometry import Point, Polygon

from ..models import CoordSystem, ParcelSearchResult
from . import mock_data

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"


class VWorldClient:
    def __init__(self, api_key: str | None = None, use_mock: bool | None = None):
        self.api_key = api_key or os.environ.get("VWORLD_API_KEY", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.api_key)

    def search_parcel(self, address: str) -> ParcelSearchResult:
        if self.use_mock:
            return mock_data.mock_search_parcel(address)

        params = {
            "service": "search",
            "request": "search",
            "query": address,
            "type": "address",
            "category": "parcel",
            "format": "json",
            "crs": "EPSG:5186",
            "key": self.api_key,
        }
        response = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_search_response(response.json(), address)

    def download_cadastral(self, result: ParcelSearchResult) -> tuple[list, int]:
        if self.use_mock:
            return mock_data.mock_cadastral_parcels(result)

        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN",
            "key": self.api_key,
            "geomFilter": f"POINT({result.x} {result.y})",
            "format": "json",
            "crs": "EPSG:5186",
            "size": "100",
        }
        response = requests.get(VWORLD_DATA_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_cadastral_response(response.json(), result)


def _parse_search_response(data: dict, address: str) -> ParcelSearchResult:
    items = data.get("response", {}).get("result", {}).get("items", [])
    if not items:
        raise ValueError(f"'{address}'에 해당하는 지번을 찾을 수 없습니다")
    item = items[0]
    point = item["point"]
    return ParcelSearchResult(
        pnu=item.get("id", ""),
        address=item.get("address", {}).get("road", address),
        x=float(point["x"]),
        y=float(point["y"]),
        coord_system=CoordSystem.GRS80_MID,
    )


def _parse_cadastral_response(data: dict, result: ParcelSearchResult) -> tuple[list[Polygon], int]:
    features = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
    if not features:
        raise ValueError(f"'{result.pnu}' 주변에서 지적 필지를 찾을 수 없습니다")

    parcels: list[Polygon] = []
    target_index = None
    for idx, feature in enumerate(features):
        coords = feature["geometry"]["coordinates"][0]
        polygon = Polygon(coords)
        parcels.append(polygon)
        if feature.get("properties", {}).get("pnu") == result.pnu:
            target_index = idx

    if target_index is None:
        point = Point(result.x, result.y)
        for idx, polygon in enumerate(parcels):
            if polygon.contains(point):
                target_index = idx
                break

    if target_index is None:
        raise ValueError(f"'{result.pnu}'에 해당하는 필지를 찾지 못했습니다")

    return parcels, target_index
