import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from jibeon_cad_tool.ui.app import build_application


def test_build_application_returns_app_and_window():
    app, window = build_application(show=False)
    assert app is not None
    assert window.windowTitle() == "지번 기반 CAD 내보내기"
