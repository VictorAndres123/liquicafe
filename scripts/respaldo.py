"""Copia de seguridad de la base de datos (mitigación del riesgo R-3).

El PC de la bodega es un punto único de falla. Este script hace una copia
consistente aunque el sistema esté en uso, porque usa la API de respaldo de
SQLite en lugar de copiar el archivo (copiar a mano un archivo en modo WAL
puede dejar la copia sin las últimas transacciones).

Uso (programarlo en el Programador de tareas de Windows al cierre del día):

    python scripts/respaldo.py --origen datos/liquicafe.db --destino E:/respaldos

Restaurar es copiar el último respaldo como ``datos/liquicafe.db``.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def respaldar(origen: Path, destino: Path, conservar: int = 30) -> Path:
    """Copia la base y deja solo los ``conservar`` respaldos más recientes."""
    if not origen.exists():
        raise FileNotFoundError(f"No existe la base de datos {origen}")
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"liquicafe-{datetime.now():%Y%m%d-%H%M%S}.db"

    with sqlite3.connect(origen) as fuente, sqlite3.connect(archivo) as copia:
        fuente.backup(copia)

    respaldos = sorted(destino.glob("liquicafe-*.db"))
    for viejo in respaldos[:-conservar]:
        viejo.unlink()
    return archivo


def main() -> None:
    parser = argparse.ArgumentParser(description="Respaldo de la base de datos de LiquiCafé")
    parser.add_argument("--origen", type=Path, default=Path("datos/liquicafe.db"))
    parser.add_argument("--destino", type=Path, default=Path("respaldos"))
    parser.add_argument("--conservar", type=int, default=30)
    args = parser.parse_args()
    print(f"Respaldo creado: {respaldar(args.origen, args.destino, args.conservar)}")


if __name__ == "__main__":
    main()
