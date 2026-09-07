import os
import sys
from pathlib import Path

studio_dir = Path(__file__).parent / "ngii_cad_studio"
if not studio_dir.exists():
    print(f"Error: {studio_dir} not found.")
    sys.exit(1)

os.chdir(str(studio_dir))
sys.path.insert(0, str(studio_dir))

import run
