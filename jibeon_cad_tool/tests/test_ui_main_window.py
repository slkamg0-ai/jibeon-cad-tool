import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from jibeon_cad_tool.models import BorderShape, CoordSystem, MapScale
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
    window.buffer_input.setText("75")
    window.include_topo_checkbox.setChecked(True)
    window.coord_system_combo.setCurrentIndex(
        list(CoordSystem).index(CoordSystem.UTMK)
    )
    window.border_shape_combo.setCurrentIndex(
        list(BorderShape).index(BorderShape.CIRCLE)
    )

    options = window.collect_export_options()

    assert options.buffer_meters == 75.0
    assert options.include_topo is True
    assert options.coord_system == CoordSystem.UTMK
    assert options.border_shape == BorderShape.CIRCLE


def test_append_log_adds_line_to_log_view(qapp):
    window = MainWindow()
    window.append_log("검색: 테스트 주소")
    assert "검색: 테스트 주소" in window.log_view.toPlainText()


def test_main_window_has_map_scale_combo(qapp):
    window = MainWindow()
    assert window.map_scale_combo.count() == len(MapScale)
    assert window.map_scale_combo.currentData() == MapScale.SCALE_5000


def test_collect_export_options_reflects_map_scale_selection(qapp):
    window = MainWindow()
    window.map_scale_combo.setCurrentIndex(list(MapScale).index(MapScale.SCALE_1000))

    options = window.collect_export_options()

    assert options.map_scale == MapScale.SCALE_1000


def test_main_window_has_download_folder_inputs(qapp):
    window = MainWindow()
    assert window.download_folder_label_input is not None
    assert window.download_watch_dir_input is not None


def test_collect_export_options_reflects_download_folder_inputs(qapp):
    window = MainWindow()
    window.download_folder_label_input.setText("Work")
    window.download_watch_dir_input.setText("G:\\내 드라이브\\Work")

    options = window.collect_export_options()

    assert options.download_folder_label == "Work"
    assert options.download_watch_dir == "G:\\내 드라이브\\Work"


def test_collect_export_options_download_folder_defaults_empty(qapp):
    window = MainWindow()

    options = window.collect_export_options()

    assert options.download_folder_label == ""
    assert options.download_watch_dir == ""
