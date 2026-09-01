import os
import sys

from dotenv import find_dotenv, load_dotenv

if getattr(sys, "frozen", False):
    # PyInstaller bundle: .env is packaged as a data file at the bundle root
    # (see run_app.spec, --add-data ".env;.").
    load_dotenv(os.path.join(sys._MEIPASS, ".env"))  # type: ignore[attr-defined]
else:
    # Load .env from the current working directory upward, then fall back to
    # walking up from this source file (covers running the app from a
    # different working directory than the project root).
    load_dotenv(find_dotenv(usecwd=True))
    load_dotenv(find_dotenv(filename=".env", raise_error_if_not_found=False))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
