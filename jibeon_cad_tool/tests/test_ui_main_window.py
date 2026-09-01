import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from jibeon_cad_tool.clients.vworld_client import VWorldClient
from jibeon_cad_tool.models import BorderShape, CoordSystem
from jibeon_cad_tool.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_has_required_widgets(qapp):
    window = MainWindow()
    assert window.address_input is not None
    assert window.search_button is not None
    assert window.coord_system_combo.count() == len(CoordSystem)
    assert window.border_shape_combo.count() == len(BorderShape)
    assert window.run_button is not None
    assert window.log_view is not None


def test_collect_export_options_reflects_form_values(qapp):
    window = MainWindow()
    window.range_input.setText("150")
    window.include_topo_checkbox.setChecked(True)
    window.coord_system_combo.setCurrentIndex(
        list(CoordSystem).index(CoordSystem.UTMK)
    )
    window.border_shape_combo.setCurrentIndex(
        list(BorderShape).index(BorderShape.CIRCLE)
    )

    window.label_font_combo.setCurrentIndex(1)

    options = window.collect_export_options()

    assert options.buffer_meters == 75.0
    assert options.include_topo is True
    assert options.coord_system == CoordSystem.UTMK
    assert options.border_shape == BorderShape.CIRCLE
    assert options.label_font == window.label_font_combo.currentData()


def test_append_log_adds_line_to_log_view(qapp):
    window = MainWindow()
    window.append_log("검색: 테스트 주소")
    assert "검색: 테스트 주소" in window.log_view.toPlainText()


def test_search_button_appends_result_to_log(qapp):
    window = MainWindow(vworld_client=VWorldClient(use_mock=True))
    window.address_input.setText("서울특별시 종로구 1번지")

    window._on_search_clicked()

    assert "주소 확인됨" in window.log_view.toPlainText()


def test_run_uses_custom_filename(qapp, tmp_path):
    window = MainWindow(vworld_client=VWorldClient(use_mock=True))
    window.address_input.setText("서울특별시 종로구 1번지")
    window.filename_input.setText("내지도")
    window.output_dir = str(tmp_path)

    window._on_run_clicked()

    assert os.path.exists(os.path.join(str(tmp_path), "내지도.dxf"))
    assert "지적도:" in window.log_view.toPlainText()
