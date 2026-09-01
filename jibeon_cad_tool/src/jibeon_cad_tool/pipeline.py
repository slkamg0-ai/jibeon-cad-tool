import os
import re
from dataclasses import dataclass

from shapely.geometry import MultiPolygon, Polygon

from .clients.ngii_client import NgiiClient
from .clients.vworld_client import VWorldClient
from .coords import transform_coords
from .dxf_export import build_cadastral_dxf
from .geometry import make_border
from .models import ExportOptions


def _transform_polygon(geometry, src, dst):
    if geometry.geom_type == "MultiPolygon":
        return MultiPolygon(
            [Polygon(transform_coords(list(part.exterior.coords), src, dst)) for part in geometry.geoms]
        )
    return Polygon(transform_coords(list(geometry.exterior.coords), src, dst))


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _resolve_cadastral_filename(filename: str | None, pnu: str) -> str:
    name = (filename or "").strip()
    if not name:
        return f"{pnu}_cadastral.dxf"
    name = _INVALID_FILENAME_CHARS.sub("_", name)
    if not name.lower().endswith(".dxf"):
        name = f"{name}.dxf"
    return name


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
    filename: str | None = None,
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
    parcels, labels, target_index = vworld_client.download_cadastral(search_result, options.buffer_meters)

    log.append("좌표계 변환")
    # Rebuilds from exterior coords only — interior rings (holes) are not preserved through the coordinate transform.
    transformed_parcels = [
        _transform_polygon(poly, search_result.coord_system, options.coord_system)
        for poly in parcels
    ]
    center_x, center_y = transform_coords(
        [(search_result.x, search_result.y)], search_result.coord_system, options.coord_system
    )[0]

    log.append("강조 표시 및 클리핑 및 도곽 생성 후 지적도 저장")
    clip_box = make_border(center_x, center_y, options.buffer_meters, options.border_shape)
    cadastral_filename = _resolve_cadastral_filename(filename, search_result.pnu)
    cadastral_path = os.path.join(output_dir, cadastral_filename)
    build_cadastral_dxf(
        parcels=transformed_parcels,
        target_index=target_index,
        clip_box=clip_box,
        border_shape=options.border_shape,
        center_x=center_x,
        center_y=center_y,
        buffer_meters=options.buffer_meters,
        output_path=cadastral_path,
        labels=labels,
        label_font=options.label_font,
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
