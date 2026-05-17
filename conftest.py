"""Configuração global do pytest — fixtures e paths."""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o root do projeto está no sys.path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
