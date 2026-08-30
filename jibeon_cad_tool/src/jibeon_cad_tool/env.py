from pathlib import Path

from dotenv import load_dotenv


def load_env(dotenv_path: Path | None = None) -> None:
    load_dotenv(dotenv_path=dotenv_path, override=False)
