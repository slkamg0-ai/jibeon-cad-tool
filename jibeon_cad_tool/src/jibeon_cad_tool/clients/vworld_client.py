import os

import requests
from shapely.geometry import Point, shape

from ..models import CoordSystem, ParcelSearchResult
from . import mock_data

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
CADASTRAL_LAYER = "LP_PA_CBND_BUBUN"


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
            "crs": CoordSystem.GRS80_MID.value,
            "key": self.api_key,
        }
        response = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_search_response(response.json(), address)

    def download_cadastral(
        self, result: ParcelSearchResult, buffer_meters: float = 100.0
    ) -> tuple[list, list[str], int]:
        if self.use_mock:
            return mock_data.mock_cadastral_parcels(result)

        min_x, min_y = result.x - buffer_meters, result.y - buffer_meters
        max_x, max_y = result.x + buffer_meters, result.y + buffer_meters
        params = {
            "service": "data",
            "request": "GetFeature",
            "data": CADASTRAL_LAYER,
            "key": self.api_key,
            "geomFilter": f"BOX({min_x},{min_y},{max_x},{max_y})",
            "geometry": "true",
            "attribute": "true",
            "crs": result.coord_system.value,
            "format": "json",
            "size": "1000",
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


def _parse_cadastral_response(data: dict, result: ParcelSearchResult) -> tuple[list, list[str], int]:
    response = data.get("response", {})
    if response.get("status") != "OK":
        raise ValueError(f"'{result.address}' 주변 지적도를 찾을 수 없습니다")

    features = response["result"]["featureCollection"]["features"]
    parcels = [shape(feature["geometry"]) for feature in features]
    labels = [_format_jibun(f.get("properties", {})) for f in features]

    target_index = next(
        (i for i, f in enumerate(features) if f.get("properties", {}).get("pnu") == result.pnu),
        None,
    )
    if target_index is None:
        point = Point(result.x, result.y)
        target_index = next(
            (i for i, poly in enumerate(parcels) if poly.contains(point)), 0
        )
    return parcels, labels, target_index


def _format_jibun(properties: dict) -> str:
    # VWorld already formats this as "본번-부번+지목약칭" (e.g. "2736-3대", "1694-1639답"),
    # matching standard 지적도 labeling, so it's used as-is.
    return properties.get("jibun", "")
