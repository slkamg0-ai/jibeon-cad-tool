import pytest

from jibeon_cad_tool.models import CoordSystem
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
    parcels, target_index = client.download_cadastral(search_result, CoordSystem.GRS80_MID)
    assert len(parcels) >= 1
    target = parcels[target_index]
    assert target.contains(target.centroid)


def test_download_cadastral_without_mock_raises_not_implemented():
    client = VWorldClient(api_key="dummy-key", use_mock=False)
    search_result = mock_data.mock_search_parcel("테스트")
    with pytest.raises(NotImplementedError):
        client.download_cadastral(search_result, CoordSystem.GRS80_MID)
