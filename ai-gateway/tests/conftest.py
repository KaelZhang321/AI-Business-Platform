from __future__ import annotations

import sys
from pathlib import Path


AI_GATEWAY_ROOT = Path(__file__).resolve().parents[1]

if str(AI_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_GATEWAY_ROOT))
