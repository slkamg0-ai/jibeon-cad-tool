import os
from pathlib import Path

from .ngii_selectors import NgiiSelectors, load_selectors

DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "ngii_selectors.json"


class NgiiWebClient:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        use_mock: bool | None = None,
        selectors: NgiiSelectors | None = None,
    ):
        self.username = username or os.environ.get("NGII_USERNAME", "")
        self.password = password or os.environ.get("NGII_PASSWORD", "")
        self.use_mock = use_mock if use_mock is not None else not bool(self.username and self.password)
        self.selectors = selectors or load_selectors(DEFAULT_SELECTORS_PATH)

    def _login(self, page) -> None:
        page.goto(self.selectors.login_url)
        page.click(self.selectors.login_trigger_selector)
        if not page.locator(self.selectors.username_selector).is_visible():
            raise RuntimeError("국토정보플랫폼 로그인 폼을 찾을 수 없습니다")
        page.fill(self.selectors.username_selector, self.username)
        page.fill(self.selectors.password_selector, self.password)
        page.click(self.selectors.login_submit_selector)
