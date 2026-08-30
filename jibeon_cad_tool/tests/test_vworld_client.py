import pytest

from jibeon_cad_tool.models import CoordSystem, ParcelSearchResult
from jibeon_cad_tool.clients import mock_data
from jibeon_cad_tool.clients.vworld_client import VWorldClient, VWORLD_SEARCH_URL, VWORLD_DATA_URL


def test_search_parcel_mock_mode_returns_result():
    client = VWorldClient(use_mock=True)
    result = client.search_parcel("서울특별시 종로구 1번지")
    assert result.address == "서울특별시 종로구 1번지"
    assert result.pnu
    assert result.coord_system == CoordSystem.GRS80_MID


def test_download_cadastral_mock_mode_includes_target_parcel():
    client = VWorldClient(use_mock=True)
    search_result = client.search_parcel("서울특별시 종로구 1번지")
    parcels, target_index = client.download_cadastral(search_result)
    assert len(parcels) >= 1
    target = parcels[target_index]
    assert target.contains(target.centroid)


def test_vworld_client_defaults_to_mock_when_no_api_key(monkeypatch):
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    client = VWorldClient()
    assert client.use_mock is True


def test_search_parcel_real_mode_sends_crs_param(requests_mock):
    requests_mock.get(
        VWORLD_SEARCH_URL,
        json={
            "response": {
                "result": {
                    "items": [
                        {
                            "id": "1111010100100010000",
                            "address": {"road": "서울특별시 종로구 1"},
                            "point": {"x": "198000.0", "y": "453000.0"},
                        }
                    ]
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    result = client.search_parcel("서울특별시 종로구 1")

    assert result.pnu == "1111010100100010000"
    assert result.coord_system == CoordSystem.GRS80_MID
    sent_crs = requests_mock.last_request.qs.get("crs")
    assert sent_crs == ["epsg:5186"]


def test_search_parcel_real_mode_raises_when_no_items(requests_mock):
    requests_mock.get(
        VWORLD_SEARCH_URL,
        json={"response": {"result": {"items": []}}},
    )

    client = VWorldClient(api_key="real-key", use_mock=False)

    with pytest.raises(ValueError):
        client.search_parcel("존재하지 않는 주소")


def test_download_cadastral_real_mode_parses_multipolygon_geometry(requests_mock):
    search_result = ParcelSearchResult(
        pnu="4159132021106710000", address="경기도 화성시 송산면 사강리 671", x=176453.9, y=512757.6,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={
            "response": {
                "result": {
                    "featureCollection": {
                        "features": [
                            {
                                "properties": {"pnu": "4159132021106710000"},
                                "geometry": {
                                    "type": "MultiPolygon",
                                    "coordinates": [
                                        [[[176440.0, 512740.0], [176470.0, 512740.0], [176470.0, 512774.0], [176440.0, 512774.0], [176440.0, 512740.0]]]
                                    ],
                                },
                            }
                        ]
                    }
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    parcels, target_index = client.download_cadastral(search_result)

    assert len(parcels) == 1
    assert target_index == 0
    assert parcels[0].contains(parcels[0].centroid)


def test_download_cadastral_real_mode_parses_feature_collection(requests_mock):
    search_result = ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={
            "response": {
                "result": {
                    "featureCollection": {
                        "features": [
                            {
                                "properties": {"pnu": "1111010100100010000"},
                                "geometry": {
                                    "coordinates": [
                                        [[197990.0, 452990.0], [198010.0, 452990.0], [198010.0, 453010.0], [197990.0, 453010.0], [197990.0, 452990.0]]
                                    ]
                                },
                            },
                            {
                                "properties": {"pnu": "1111010100100020000"},
                                "geometry": {
                                    "coordinates": [
                                        [[198050.0, 452990.0], [198070.0, 452990.0], [198070.0, 453010.0], [198050.0, 453010.0], [198050.0, 452990.0]]
                                    ]
                                },
                            },
                        ]
                    }
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    parcels, target_index = client.download_cadastral(search_result)

    assert len(parcels) == 2
    assert target_index == 0
    assert parcels[0].contains(parcels[0].centroid)


def test_download_cadastral_real_mode_falls_back_to_spatial_containment(requests_mock):
    search_result = ParcelSearchResult(
        pnu="9999999999999999999", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={
            "response": {
                "result": {
                    "featureCollection": {
                        "features": [
                            {
                                "properties": {"pnu": "1111010100100010000"},
                                "geometry": {
                                    "coordinates": [
                                        [[197990.0, 452990.0], [198010.0, 452990.0], [198010.0, 453010.0], [197990.0, 453010.0], [197990.0, 452990.0]]
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        },
    )

    client = VWorldClient(api_key="real-key", use_mock=False)
    parcels, target_index = client.download_cadastral(search_result)

    assert target_index == 0


def test_download_cadastral_real_mode_raises_when_no_features(requests_mock):
    search_result = ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    requests_mock.get(
        VWORLD_DATA_URL,
        json={"response": {"result": {"featureCollection": {"features": []}}}},
    )

    client = VWorldClient(api_key="real-key", use_mock=False)

    with pytest.raises(ValueError):
        client.download_cadastral(search_result)
