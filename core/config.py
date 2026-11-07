"""Configuración leída del entorno, con valores por defecto sensatos."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def ruta_base_datos() -> Path:
    """Base SQLite local. Se puede cambiar con la variable FINTWIN_DB."""
    return Path(os.environ.get("FINTWIN_DB", RAIZ / "data" / "fintwin.db"))
