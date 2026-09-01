from jibeon_cad_tool.models import CoordSystem, ParcelSearchResult
from jibeon_cad_tool.clients import mock_data
from jibeon_cad_tool.clients.vworld_client import VWorldClient


def test_search_parcel_mock_mode_returns_result():
    client = VWorldClient(use_mock=True)
    result = client.search_parcel("서울특별시 종로구 1번지")
    assert result.address == "서울특별시 종로구 1번지"
    assert result.pnu
    assert result.coord_system == CoordSystem.GRS80_MID


def test_download_cadastral_mock_mode_includes_target_parcel():
    client = VWorldClient(use_mock=True)
    search_result = client.search_parcel("서울특별시 종로구 1번지")
    parcels, labels, target_index = client.download_cadastral(search_result)
    assert len(parcels) >= 1
    assert len(labels) == len(parcels)
    target = parcels[target_index]
    assert target.contains(target.centroid)


def test_download_cadastral_real_api_finds_target_by_pnu(monkeypatch):
    client = VWorldClient(api_key="dummy-key", use_mock=False)
    search_result = ParcelSearchResult(
        pnu="4122012800127280000",
        address="고덕동 2728",
        x=958450.0,
        y=1892300.0,
        coord_system=CoordSystem.KATEC,
    )

    fake_response = {
        "response": {
            "status": "OK",
            "result": {
                "featureCollection": {
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                            },
                            "properties": {"pnu": "9999999999999999999", "jibun": "1대"},
                        },
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[20, 0], [30, 0], [30, 10], [20, 10], [20, 0]]],
                            },
                            "properties": {"pnu": "4122012800127280000", "jibun": "2728-3대"},
                        },
                    ]
                }
            },
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_response

    monkeypatch.setattr(
        "jibeon_cad_tool.clients.vworld_client.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )

    parcels, labels, target_index = client.download_cadastral(search_result)
    assert len(parcels) == 2
    assert target_index == 1
    assert labels[1] == "2728-3대"


def test_vworld_client_defaults_to_mock_when_no_api_key(monkeypatch):
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    client = VWorldClient()
    assert client.use_mock is True
