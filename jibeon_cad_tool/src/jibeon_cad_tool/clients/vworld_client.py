import os

import requests

from ..models import CoordSystem, ParcelSearchResult
from . import mock_data

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"


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
            "key": self.api_key,
        }
        response = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        return _parse_search_response(response.json(), address)

    def download_cadastral(
        self, result: ParcelSearchResult, coord_system: CoordSystem
    ) -> tuple[list, int]:
        if self.use_mock:
            return mock_data.mock_cadastral_parcels(result, coord_system)
        raise NotImplementedError(
            "실 API 지적도 다운로드 엔드포인트는 API 키 발급 후 연동 예정"
        )


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
