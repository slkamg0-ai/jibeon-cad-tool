import os

from jibeon_cad_tool.models import BorderShape, CoordSystem, ExportOptions
from jibeon_cad_tool.clients.vworld_client import VWorldClient
from jibeon_cad_tool.clients.ngii_client import NgiiClient
from jibeon_cad_tool.pipeline import run_pipeline


def test_run_pipeline_cadastral_only(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID, buffer_meters=30.0)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    assert os.path.exists(result.cadastral_path)
    assert result.topo_path is None
    assert result.ortho_path is None
    assert "완료" in result.log[-1]


def test_run_pipeline_with_topo_and_ortho(tmp_path):
    options = ExportOptions(
        coord_system=CoordSystem.UTMK,
        buffer_meters=50.0,
        border_shape=BorderShape.CIRCLE,
        include_topo=True,
        include_ortho=True,
    )
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    assert os.path.exists(result.cadastral_path)
    assert os.path.exists(result.topo_path)
    assert os.path.exists(result.ortho_path)


def test_run_pipeline_with_custom_filename(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID, buffer_meters=30.0)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        filename="내지도",
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    assert result.cadastral_path == os.path.join(str(tmp_path), "내지도.dxf")
    assert os.path.exists(result.cadastral_path)


def test_run_pipeline_sanitizes_unsafe_filename_chars(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID, buffer_meters=30.0)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        filename="a/b:c.dxf",
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    assert os.path.basename(result.cadastral_path) == "a_b_c.dxf"
    assert os.path.exists(result.cadastral_path)


def test_run_pipeline_logs_each_stage(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiClient(use_mock=True),
    )
    joined_log = " ".join(result.log)
    assert "검색" in joined_log
    assert "지적도 다운로드" in joined_log
    assert "좌표계 변환" in joined_log
