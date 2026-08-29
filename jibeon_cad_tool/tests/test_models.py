from jibeon_cad_tool.models import CoordSystem, BorderShape, ParcelSearchResult, ExportOptions


def test_coord_system_values():
    assert CoordSystem.GRS80_MID.value == "EPSG:5186"
    assert CoordSystem.UTMK.value == "EPSG:5179"


def test_export_options_defaults():
    options = ExportOptions(coord_system=CoordSystem.GRS80_MID)
    assert options.buffer_meters == 100.0
    assert options.border_shape == BorderShape.RECTANGLE
    assert options.include_topo is False
    assert options.include_ortho is False


def test_parcel_search_result_fields():
    result = ParcelSearchResult(
        pnu="1111010100100010000", address="서울 종로구 1", x=198000.0, y=453000.0,
        coord_system=CoordSystem.GRS80_MID,
    )
    assert result.pnu == "1111010100100010000"
    assert result.x == 198000.0
