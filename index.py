import sys
import os
from pathlib import Path

# Ensure project root directory is in sys.path for Vercel Serverless Function
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.server_thienminh import create_thienminh_app

app = create_thienminh_app()
