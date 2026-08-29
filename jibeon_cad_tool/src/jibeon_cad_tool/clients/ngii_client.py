import os
from dataclasses import dataclass

from ..models import CoordSystem, ParcelSearchResult


@dataclass
class RasterDownloadResult:
    file_path: str
    coord_system: CoordSystem


class NgiiClient:
    def __init__(self, api_key: str | None = None, use_mock: bool | None = None):
        self.api_key = api_key or os.environ.get("NGII_API_KEY", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.api_key)

    def download_topo(
        self, result: ParcelSearchResult, coord_system: CoordSystem, output_path: str
    ) -> RasterDownloadResult:
        if self.use_mock:
            _write_mock_raster_stub(output_path, "TOPO", result, coord_system)
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)
        raise NotImplementedError(
            "실 API 수치지형도 다운로드 엔드포인트는 API 키 발급 후 연동 예정"
        )

    def download_ortho(
        self, result: ParcelSearchResult, coord_system: CoordSystem, output_path: str
    ) -> RasterDownloadResult:
        if self.use_mock:
            _write_mock_raster_stub(output_path, "ORTHO", result, coord_system)
            return RasterDownloadResult(file_path=output_path, coord_system=coord_system)
        raise NotImplementedError(
            "실 API 정사영상 다운로드 엔드포인트는 API 키 발급 후 연동 예정"
        )


def _write_mock_raster_stub(
    output_path: str, kind: str, result: ParcelSearchResult, coord_system: CoordSystem
) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(
            f"{kind} mock raster\n"
            f"pnu={result.pnu}\n"
            f"x={result.x}\n"
            f"y={result.y}\n"
            f"coord_system={coord_system.value}\n"
        )
