# -*- coding: utf-8 -*-
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
STUDIO_DIR = REPO_ROOT / "ngii_cad_studio"

for p in (str(REPO_ROOT), str(STUDIO_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ngii_cad_studio.app.main import app
