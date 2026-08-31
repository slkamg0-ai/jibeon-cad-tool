from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
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

from ..models import BorderShape, CoordSystem, ExportOptions, MapScale
from ..pipeline import run_pipeline

COORD_SYSTEM_LABELS = {
    CoordSystem.GRS80_MID: "GRS80 중부원점 (EPSG:5186)",
    CoordSystem.GRS80_WEST: "GRS80 서부원점 (EPSG:5185)",
    CoordSystem.GRS80_EAST: "GRS80 동부원점 (EPSG:5187)",
    CoordSystem.UTMK: "UTM-K (EPSG:5179)",
}

BORDER_SHAPE_LABELS = {
    BorderShape.RECTANGLE: "사각형",
    BorderShape.CIRCLE: "원형",
}

MAP_SCALE_LABELS = {
    MapScale.SCALE_5000: "1:5,000",
    MapScale.SCALE_1000: "1:1,000",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("지번 기반 CAD 내보내기")
        self.output_dir = "."

        self.address_input = QLineEdit()
        self.search_button = QPushButton("검색")

        self.coord_system_combo = QComboBox()
        for coord_system in CoordSystem:
            self.coord_system_combo.addItem(COORD_SYSTEM_LABELS[coord_system], coord_system)

        self.include_topo_checkbox = QCheckBox("지형도 다운로드")
        self.include_ortho_checkbox = QCheckBox("정사영상 다운로드")

        self.buffer_input = QLineEdit("100")

        self.border_shape_combo = QComboBox()
        for border_shape in BorderShape:
            self.border_shape_combo.addItem(BORDER_SHAPE_LABELS[border_shape], border_shape)

        self.map_scale_combo = QComboBox()
        for map_scale in MapScale:
            self.map_scale_combo.addItem(MAP_SCALE_LABELS[map_scale], map_scale)

        self.download_folder_label_input = QLineEdit()
        self.download_folder_label_input.setPlaceholderText("국토정보플랫폼에 미리 등록해둔 폴더명 (예: Work)")
        self.download_watch_dir_input = QLineEdit()
        self.download_watch_dir_input.setPlaceholderText("그 폴더의 로컬 경로 (예: G:\\내 드라이브\\Work)")

        self.run_button = QPushButton("실행")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.open_folder_button = QPushButton("폴더 열기")

        self.run_button.clicked.connect(self._on_run_clicked)

        form_layout = QFormLayout()
        address_row = QHBoxLayout()
        address_row.addWidget(self.address_input)
        address_row.addWidget(self.search_button)
        form_layout.addRow("지번:", address_row)
        form_layout.addRow("좌표계:", self.coord_system_combo)
        form_layout.addRow(self.include_topo_checkbox)
        form_layout.addRow(self.include_ortho_checkbox)
        form_layout.addRow("버퍼 거리(m):", self.buffer_input)
        form_layout.addRow("도곽 형태:", self.border_shape_combo)
        form_layout.addRow("축척:", self.map_scale_combo)
        form_layout.addRow("NGII 저장 폴더명:", self.download_folder_label_input)
        form_layout.addRow("NGII 로컬 감시 경로:", self.download_watch_dir_input)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.run_button)
        layout.addWidget(QLabel("진행 로그:"))
        layout.addWidget(self.log_view)
        layout.addWidget(self.open_folder_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def collect_export_options(self) -> ExportOptions:
        return ExportOptions(
            coord_system=self.coord_system_combo.currentData(),
            buffer_meters=float(self.buffer_input.text()),
            border_shape=self.border_shape_combo.currentData(),
            include_topo=self.include_topo_checkbox.isChecked(),
            include_ortho=self.include_ortho_checkbox.isChecked(),
            map_scale=self.map_scale_combo.currentData(),
            download_folder_label=self.download_folder_label_input.text().strip(),
            download_watch_dir=self.download_watch_dir_input.text().strip(),
        )

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _on_run_clicked(self) -> None:
        address = self.address_input.text().strip()
        if not address:
            QMessageBox.warning(self, "입력 필요", "지번을 입력해 주세요")
            return

        selected_dir = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if not selected_dir:
            return
        self.output_dir = selected_dir

        try:
            options = self.collect_export_options()
            result = run_pipeline(address=address, options=options, output_dir=self.output_dir)
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
