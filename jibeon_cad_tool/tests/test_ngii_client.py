import os

import pytest

from jibeon_cad_tool.models import CoordSystem, ParcelSearchResult
from jibeon_cad_tool.clients.ngii_client import NgiiClient


@pytest.fixture
def search_result():
    return ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )


def test_download_topo_mock_mode_writes_file(tmp_path, search_result):
    client = NgiiClient(use_mock=True)
    output_path = str(tmp_path / "topo.txt")
    result = client.download_topo(search_result, CoordSystem.GRS80_MID, output_path)
    assert result.file_path == output_path
    assert os.path.exists(output_path)
    content = open(output_path, encoding="utf-8").read()
    assert "TOPO" in content
    assert search_result.pnu in content


def test_download_ortho_mock_mode_writes_file(tmp_path, search_result):
    client = NgiiClient(use_mock=True)
    output_path = str(tmp_path / "ortho.txt")
    result = client.download_ortho(search_result, CoordSystem.UTMK, output_path)
    assert result.coord_system == CoordSystem.UTMK
    content = open(output_path, encoding="utf-8").read()
    assert "ORTHO" in content


def test_download_topo_without_mock_raises_not_implemented(search_result):
    client = NgiiClient(api_key="dummy-key", use_mock=False)
    with pytest.raises(NotImplementedError):
        client.download_topo(search_result, CoordSystem.GRS80_MID, "unused.txt")
