import os
from dataclasses import dataclass

from shapely.geometry import Polygon

from .clients.ngii_client import NgiiClient
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
    ngii_client: NgiiClient | None = None,
) -> PipelineResult:
    vworld_client = vworld_client or VWorldClient()
    ngii_client = ngii_client or NgiiClient()
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
    if options.include_topo:
        log.append("지형도 다운로드")
        topo_path = os.path.join(output_dir, f"{search_result.pnu}_topo.txt")
        ngii_client.download_topo(search_result, options.coord_system, topo_path)
    if options.include_ortho:
        log.append("정사영상 다운로드")
        ortho_path = os.path.join(output_dir, f"{search_result.pnu}_ortho.txt")
        ngii_client.download_ortho(search_result, options.coord_system, ortho_path)

    log.append("완료")
    return PipelineResult(
        cadastral_path=cadastral_path, topo_path=topo_path, ortho_path=ortho_path, log=log
    )
