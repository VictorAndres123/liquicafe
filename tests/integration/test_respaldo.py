"""El respaldo produce una base utilizable y rota los archivos viejos."""

from __future__ import annotations

import sqlite3

from app.persistence import database
from scripts.respaldo import respaldar


def test_respaldo_conserva_los_datos_y_rota(tmp_path):
    origen = tmp_path / "liquicafe.db"
    database.inicializar(origen)
    with sqlite3.connect(origen) as conexion:
        conexion.execute("INSERT INTO precios VALUES ('2026-04-09', 2220000, 10000)")

    destino = tmp_path / "respaldos"
    for indice in range(3):
        (destino / f"liquicafe-2026010{indice}-000000.db").parent.mkdir(exist_ok=True)
        (destino / f"liquicafe-2026010{indice}-000000.db").write_bytes(b"")
    copia = respaldar(origen, destino, conservar=2)

    with sqlite3.connect(copia) as conexion:
        assert conexion.execute("SELECT precio_carga_fr94 FROM precios").fetchone() == (2220000,)
    assert len(list(destino.glob("liquicafe-*.db"))) == 2
