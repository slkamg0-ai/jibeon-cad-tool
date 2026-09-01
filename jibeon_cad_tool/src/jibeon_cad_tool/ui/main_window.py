import os
import subprocess
import sys

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config  # noqa: F401 - loads .env before VWorldClient reads API keys
from ..clients.vworld_client import VWorldClient
from ..models import BorderShape, CoordSystem, ExportOptions
from ..pipeline import run_pipeline

DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "지번CAD출력")
DEFAULT_RANGE_METERS = "100"

COORD_SYSTEM_LABELS = {
    CoordSystem.GRS80_MID: "GRS80 중부원점 (EPSG:5186)",
    CoordSystem.GRS80_WEST: "GRS80 서부원점 (EPSG:5185)",
    CoordSystem.GRS80_EAST: "GRS80 동부원점 (EPSG:5187)",
    CoordSystem.UTMK: "UTM-K (EPSG:5179)",
    CoordSystem.KATEC: "KATEC (EPSG:5178)",
}

BORDER_SHAPE_LABELS = {
    BorderShape.RECTANGLE: "사각형",
    BorderShape.CIRCLE: "원형",
}

# display label -> TTF font file name (must be findable by the CAD viewer, e.g. installed on Windows)
LABEL_FONT_OPTIONS = {
    "맑은 고딕": "malgun.ttf",
    "굴림": "gulim.ttc",
    "돋움": "dotum.ttc",
    "바탕": "batang.ttc",
    "Arial": "arial.ttf",
}

# Palette borrowed from a clean SaaS reference site: navy text, teal accent,
# light-gray canvas, white cards, 6px corner radius, system-ui font stack.
STYLE_SHEET = """
* {
    font-family: "Segoe UI", system-ui, sans-serif;
}

QMainWindow, QWidget#centralContainer {
    background-color: #f2f4f7;
}

QLabel#titleLabel {
    font-size: 19px;
    font-weight: 700;
    color: #0f2b46;
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #6f6f6f;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dae1e8;
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    color: #0f2b46;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #0f2b46;
}

QLabel {
    color: #242b34;
}

QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #dbe0e5;
    border-radius: 6px;
    padding: 6px 8px;
    min-height: 20px;
    color: #0f2b46;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0177a9;
}

QLineEdit:disabled, QComboBox:disabled {
    background-color: #f2f4f7;
    color: #9ba3ac;
}

QCheckBox {
    color: #242b34;
    spacing: 8px;
}

QCheckBox:disabled {
    color: #9ba3ac;
}

QPushButton {
    background-color: #f2f4f7;
    border: 1px solid #dae1e8;
    border-radius: 6px;
    padding: 7px 14px;
    color: #292c32;
}

QPushButton:hover {
    background-color: #e0e4e9;
}

QPushButton:pressed {
    background-color: #dde2e7;
}

QPushButton:disabled {
    color: #9ba3ac;
    background-color: #f2f4f7;
}

QPushButton#runButton {
    background-color: #006494;
    border: 1px solid #006494;
    color: #ffffff;
    font-weight: 600;
    padding: 10px 16px;
    font-size: 13px;
}

QPushButton#runButton:hover {
    background-color: #0177a9;
}

QPushButton#runButton:pressed {
    background-color: #065a85;
}

QPlainTextEdit#logView {
    background-color: #0f2b46;
    color: #e0e4e9;
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-family: Consolas, 'D2Coding', monospace;
    font-size: 12px;
}

QFrame#divider {
    background-color: #dae1e8;
    max-height: 1px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, vworld_client: VWorldClient | None = None):
        super().__init__()
        self.setWindowTitle("지번 기반 CAD 내보내기")
        self.setMinimumSize(560, 680)
        self.setStyleSheet(STYLE_SHEET)
        self.output_dir = DEFAULT_OUTPUT_DIR
        self.vworld_client = vworld_client or VWorldClient()

        self._build_widgets()
        self._build_layout()

    def _build_widgets(self) -> None:
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("예: 고덕동 2728")
        self.search_button = QPushButton("주소 확인")

        self.coord_system_combo = QComboBox()
        for coord_system in CoordSystem:
            self.coord_system_combo.addItem(COORD_SYSTEM_LABELS[coord_system], coord_system)

        self.range_input = QLineEdit(DEFAULT_RANGE_METERS)
        self.range_input.setPlaceholderText("예: 100 (100m x 100m)")

        self.border_shape_combo = QComboBox()
        for border_shape in BorderShape:
            self.border_shape_combo.addItem(BORDER_SHAPE_LABELS[border_shape], border_shape)

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("비워두면 자동 지정 (예: PNU_cadastral.dxf)")

        self.label_font_combo = QComboBox()
        for display_name in LABEL_FONT_OPTIONS:
            self.label_font_combo.addItem(display_name, LABEL_FONT_OPTIONS[display_name])

        self.include_topo_checkbox = QCheckBox("지형도 다운로드 (준비 중)")
        self.include_topo_checkbox.setEnabled(False)
        self.include_topo_checkbox.setToolTip("국토정보플랫폼 실 API 연동 전이라 아직 사용할 수 없습니다")
        self.include_ortho_checkbox = QCheckBox("정사영상 다운로드 (준비 중)")
        self.include_ortho_checkbox.setEnabled(False)
        self.include_ortho_checkbox.setToolTip("국토정보플랫폼 실 API 연동 전이라 아직 사용할 수 없습니다")

        self.output_dir_label = QLabel(DEFAULT_OUTPUT_DIR)
        self.output_dir_label.setWordWrap(True)
        self.output_dir_button = QPushButton("폴더 변경")

        self.run_button = QPushButton("DXF 생성")
        self.run_button.setObjectName("runButton")

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)

        self.open_folder_button = QPushButton("저장 폴더 열기")

        self.search_button.clicked.connect(self._on_search_clicked)
        self.output_dir_button.clicked.connect(self._on_select_output_dir_clicked)
        self.run_button.clicked.connect(self._on_run_clicked)
        self.open_folder_button.clicked.connect(self._on_open_folder_clicked)

    def _build_layout(self) -> None:
        title_label = QLabel("지번 기반 CAD 내보내기")
        title_label.setObjectName("titleLabel")
        subtitle_label = QLabel("주소를 입력하면 지정한 범위의 연속지적도를 DXF로 내려받습니다")
        subtitle_label.setObjectName("subtitleLabel")

        search_group = QGroupBox("주소 검색")
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.address_input)
        search_layout.addWidget(self.search_button)
        search_group.setLayout(search_layout)

        options_group = QGroupBox("내보내기 옵션")
        options_layout = QFormLayout()
        options_layout.setSpacing(10)
        options_layout.addRow("좌표계:", self.coord_system_combo)
        options_layout.addRow("범위 (가로x세로, m):", self.range_input)
        options_layout.addRow("도곽 형태:", self.border_shape_combo)
        options_layout.addRow("저장 파일명:", self.filename_input)
        options_layout.addRow("지번 텍스트 폰트:", self.label_font_combo)
        options_layout.addRow(self.include_topo_checkbox)
        options_layout.addRow(self.include_ortho_checkbox)
        options_group.setLayout(options_layout)

        output_group = QGroupBox("저장 위치")
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_label, stretch=1)
        output_layout.addWidget(self.output_dir_button)
        output_group.setLayout(output_layout)

        log_group = QGroupBox("진행 로그")
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_view)
        log_layout.addWidget(self.open_folder_button)
        log_group.setLayout(log_layout)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(divider)
        layout.addWidget(search_group)
        layout.addWidget(options_group)
        layout.addWidget(output_group)
        layout.addWidget(self.run_button)
        layout.addWidget(log_group, stretch=1)

        container = QWidget()
        container.setObjectName("centralContainer")
        container.setLayout(layout)
        self.setCentralWidget(container)

    def collect_export_options(self) -> ExportOptions:
        return ExportOptions(
            coord_system=self.coord_system_combo.currentData(),
            buffer_meters=float(self.range_input.text()) / 2,
            border_shape=self.border_shape_combo.currentData(),
            include_topo=self.include_topo_checkbox.isChecked(),
            include_ortho=self.include_ortho_checkbox.isChecked(),
            label_font=self.label_font_combo.currentData(),
        )

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _on_search_clicked(self) -> None:
        address = self.address_input.text().strip()
        if not address:
            QMessageBox.warning(self, "입력 필요", "주소/지번을 입력해 주세요")
            return

        try:
            result = self.vworld_client.search_parcel(address)
        except Exception as exc:  # noqa: BLE001 - surface any search failure to the user
            self.append_log(f"주소 확인 실패: {exc}")
            QMessageBox.critical(self, "주소 확인 실패", str(exc))
            return

        self.append_log(f"주소 확인됨: {result.address} (PNU: {result.pnu})")

    def _on_select_output_dir_clicked(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if not selected_dir:
            return
        self.output_dir = selected_dir
        self.output_dir_label.setText(selected_dir)

    def _on_open_folder_clicked(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(self.output_dir)  # noqa: S606 - opening a local folder the user chose
        elif sys.platform == "darwin":
            subprocess.run(["open", self.output_dir], check=False)
        else:
            subprocess.run(["xdg-open", self.output_dir], check=False)

    def _on_run_clicked(self) -> None:
        address = self.address_input.text().strip()
        if not address:
            QMessageBox.warning(self, "입력 필요", "주소/지번을 입력해 주세요")
            return

        try:
            options = self.collect_export_options()
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "범위(m)는 숫자로 입력해 주세요")
            return

        try:
            result = run_pipeline(
                address=address,
                options=options,
                output_dir=self.output_dir,
                filename=self.filename_input.text().strip() or None,
                vworld_client=self.vworld_client,
            )
        except Exception as exc:  # noqa: BLE001 - surface any pipeline failure to the user
            self.append_log(f"실패: {exc}")
            QMessageBox.critical(self, "실행 실패", str(exc))
            return

        for message in result.log:
            self.append_log(message)
        self.append_log(f"지적도: {result.cadastral_path}")
        if result.topo_path:
            self.append_log(f"지형도: {result.topo_path}")
        if result.ortho_path:
            self.append_log(f"정사영상: {result.ortho_path}")
