import os

from jibeon_cad_tool.models import BorderShape, CoordSystem, ExportOptions, MapScale
from jibeon_cad_tool.clients.vworld_client import VWorldClient
from jibeon_cad_tool.clients.ngii_web_client import NgiiWebClient
from jibeon_cad_tool.pipeline import run_pipeline


def test_run_pipeline_cadastral_only(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID, buffer_meters=30.0)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiWebClient(use_mock=True),
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
        ngii_client=NgiiWebClient(use_mock=True),
    )
    assert os.path.exists(result.cadastral_path)
    assert os.path.exists(result.topo_path)
    assert os.path.exists(result.ortho_path)


def test_run_pipeline_logs_each_stage(tmp_path):
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=NgiiWebClient(use_mock=True),
    )
    joined_log = " ".join(result.log)
    assert "검색" in joined_log
    assert "지적도 다운로드" in joined_log
    assert "좌표계 변환" in joined_log


def test_run_pipeline_passes_map_scale_and_handles_pending_ortho(tmp_path, monkeypatch):
    class _StubNgiiClient:
        def __init__(self):
            self.use_mock = True

        def download_topo(self, result, coord_system, map_scale, sheet_features, output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("TOPO stub\n")
            from jibeon_cad_tool.clients.ngii_client import RasterDownloadResult
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

        def download_ortho(self, result, coord_system, map_scale, sheet_features, output_path, **_kwargs):
            return None

    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        map_scale=MapScale.SCALE_5000,
        include_topo=True,
        include_ortho=True,
    )
    result = run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=_StubNgiiClient(),
    )

    assert result.topo_path is not None
    assert result.ortho_path is None
    assert any("대기" in line for line in result.log)


def test_run_pipeline_passes_download_folder_overrides_to_default_ngii_client(tmp_path, monkeypatch):
    captured_kwargs = {}

    class _CapturingNgiiWebClient:
        def __init__(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            self.use_mock = True

        def download_topo(self, result, coord_system, map_scale, sheet_features, output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("TOPO stub\n")
            from jibeon_cad_tool.clients.ngii_client import RasterDownloadResult
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

        def download_ortho(self, result, coord_system, map_scale, sheet_features, output_path, **_kwargs):
            return None

    monkeypatch.setattr("jibeon_cad_tool.pipeline.NgiiWebClient", _CapturingNgiiWebClient)

    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        include_topo=True,
        download_folder_label="Work",
        download_watch_dir="/custom/watch",
    )
    run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
    )

    assert captured_kwargs.get("download_folder_label") == "Work"
    assert captured_kwargs.get("download_watch_dir") == "/custom/watch"


def test_run_pipeline_does_not_override_explicitly_injected_ngii_client(tmp_path):
    class _StubNgiiClient:
        def __init__(self):
            self.use_mock = True
            self.received_init_kwargs = None

        def download_topo(self, result, coord_system, map_scale, sheet_features, output_path):
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("TOPO stub\n")
            from jibeon_cad_tool.clients.ngii_client import RasterDownloadResult
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)

    stub = _StubNgiiClient()
    options = ExportOptions(
        coord_system=CoordSystem.GRS80_MID,
        include_topo=True,
        download_folder_label="Work",
        download_watch_dir="/custom/watch",
    )
    run_pipeline(
        address="서울특별시 종로구 1번지",
        options=options,
        output_dir=str(tmp_path),
        vworld_client=VWorldClient(use_mock=True),
        ngii_client=stub,
    )

    assert stub.received_init_kwargs is None
