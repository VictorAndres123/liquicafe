"""Función de aptitud de la arquitectura (fitness function).

Ejecuta los contratos de import-linter definidos en ``pyproject.toml``. Si un
día alguien hace que una ruta consulte SQLite directamente, o que el dominio
importe FastAPI, esta prueba falla aunque todo lo demás funcione.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("lint-imports") is None, reason="import-linter no está instalado")
def test_los_contratos_de_capas_se_cumplen():
    resultado = subprocess.run(["lint-imports"], cwd=RAIZ, capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
