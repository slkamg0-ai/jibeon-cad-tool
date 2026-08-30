import os
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Polygon

from .clients.ngii_web_client import NgiiWebClient
from .clients.vworld_client import VWorldClient
from .coords import transform_coords
from .dxf_export import build_cadastral_dxf
from .geometry import make_buffer_box
from .models import ExportOptions


@dataclass
class PipelineResult:
    cadastral_path: str
    topo_path: str | None
    ortho_path: str | None
    log: list[str]


def run_pipeline(
    address: str,
    options: ExportOptions,
    output_dir: str,
    vworld_client: VWorldClient | None = None,
    ngii_client: NgiiWebClient | None = None,
) -> PipelineResult:
    vworld_client = vworld_client or VWorldClient()
    if ngii_client is None:
        ngii_kwargs = {}
        if options.download_folder_label:
            ngii_kwargs["download_folder_label"] = options.download_folder_label
        if options.download_watch_dir:
            ngii_kwargs["download_watch_dir"] = options.download_watch_dir
        ngii_client = NgiiWebClient(**ngii_kwargs)
    log: list[str] = []
    os.makedirs(output_dir, exist_ok=True)

    log.append(f"검색: {address}")
    search_result = vworld_client.search_parcel(address)

    log.append("지적도 다운로드")
    parcels, target_index = vworld_client.download_cadastral(search_result)

    log.append("좌표계 변환")
    # Rebuilds from exterior coords only — interior rings (holes) are not preserved through the coordinate transform.
    transformed_parcels = [
        Polygon(transform_coords(list(poly.exterior.coords), search_result.coord_system, options.coord_system))
        for poly in parcels
    ]
    center_x, center_y = transform_coords(
        [(search_result.x, search_result.y)], search_result.coord_system, options.coord_system
    )[0]

    log.append("강조 표시 및 클리핑 및 도곽 생성 후 지적도 저장")
    clip_box = make_buffer_box(center_x, center_y, options.buffer_meters)
    cadastral_path = os.path.join(output_dir, f"{search_result.pnu}_cadastral.dxf")
    build_cadastral_dxf(
        parcels=transformed_parcels,
        target_index=target_index,
        clip_box=clip_box,
        border_shape=options.border_shape,
        center_x=center_x,
        center_y=center_y,
        buffer_meters=options.buffer_meters,
        output_path=cadastral_path,
    )

    topo_path = None
    ortho_path = None
    if options.include_topo or options.include_ortho:
        sheet_features = _load_sheet_features_for_client(ngii_client)

    if options.include_topo:
        log.append("지형도 다운로드")
        topo_path = os.path.join(output_dir, f"{search_result.pnu}_topo.txt")
        ngii_client.download_topo(
            search_result, options.coord_system, options.map_scale, sheet_features, topo_path
        )
    if options.include_ortho:
        log.append("정사영상 다운로드")
        ortho_output_path = os.path.join(output_dir, f"{search_result.pnu}_ortho.txt")
        ortho_result = ngii_client.download_ortho(
            search_result, options.coord_system, options.map_scale, sheet_features, ortho_output_path
        )
        if ortho_result is not None:
            ortho_path = ortho_result.file_path
        else:
            log.append("정사영상 신청 완료 — 승인 대기 중이라 지금은 다운로드하지 못했습니다. 나중에 국토정보플랫폼에서 직접 확인하세요")

    log.append("완료")
    return PipelineResult(
        cadastral_path=cadastral_path, topo_path=topo_path, ortho_path=ortho_path, log=log
    )


def _load_sheet_features_for_client(ngii_client) -> list[dict]:
    if getattr(ngii_client, "use_mock", True):
        return []
    from .map_sheet_index import load_index

    default_index_path = Path(__file__).resolve().parent.parent.parent / "data" / "map_sheet_index_fixture.geojson"
    return load_index(default_index_path)
