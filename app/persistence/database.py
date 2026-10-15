"""Conexión a SQLite y unidad de trabajo.

Elegí SQLite porque la asociación no tiene presupuesto ni quien administre un
motor de base de datos: es un archivo en el PC de la bodega y se respalda
copiándolo. Para que un corte de luz no deje liquidaciones a medias
(escenario QA-05), la base trabaja en modo WAL y cada caso de uso corre
dentro de una transacción explícita que abre ``UnidadDeTrabajo``.

Los triggers son una segunda línea de defensa de la regla RN-11: aunque
alguien abra el archivo con otra herramienta, no puede borrar una
liquidación ni cambiar sus valores.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from app.persistence.repositories import (
    RepositorioAuditoria,
    RepositorioLiquidaciones,
    RepositorioPrecios,
    RepositorioProductores,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productores (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    cedula                   TEXT    NOT NULL UNIQUE,
    nombre                   TEXT    NOT NULL,
    vereda                   TEXT    NOT NULL,
    telefono                 TEXT,
    programa_especial        INTEGER NOT NULL DEFAULT 0,
    fecha_autorizacion_datos TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS precios (
    fecha             TEXT    PRIMARY KEY,
    precio_carga_fr94 INTEGER NOT NULL CHECK (precio_carga_fr94 > 0),
    precio_pasilla_kg INTEGER NOT NULL CHECK (precio_pasilla_kg > 0)
);

-- kilos, humedad y factor se guardan como TEXT: SQLite no tiene tipo
-- decimal y REAL convertiría 190.3 en 190.30000000000001.
CREATE TABLE IF NOT EXISTS liquidaciones (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    productor_id          INTEGER NOT NULL REFERENCES productores(id),
    fecha                 TEXT    NOT NULL,
    kilos                 TEXT    NOT NULL,
    humedad               TEXT    NOT NULL,
    factor_rendimiento    TEXT    NOT NULL,
    defecto               TEXT    NOT NULL,
    precio_kg             INTEGER NOT NULL,
    lineas                TEXT    NOT NULL,
    neto                  INTEGER NOT NULL,
    parametros            TEXT    NOT NULL,
    estado                TEXT    NOT NULL,
    motivo_anulacion      TEXT,
    responsable_anulacion TEXT
);

CREATE INDEX IF NOT EXISTS ix_liquidaciones_fecha ON liquidaciones(fecha);
CREATE INDEX IF NOT EXISTS ix_liquidaciones_productor ON liquidaciones(productor_id);

CREATE TABLE IF NOT EXISTS auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    liquidacion_id  INTEGER NOT NULL REFERENCES liquidaciones(id),
    evento          TEXT    NOT NULL,
    detalle         TEXT,
    responsable     TEXT    NOT NULL,
    momento         TEXT    NOT NULL
);

CREATE TRIGGER IF NOT EXISTS liquidaciones_no_se_borran
BEFORE DELETE ON liquidaciones
BEGIN
    SELECT RAISE(ABORT, 'Las liquidaciones no se borran: se anulan (RN-11)');
END;

CREATE TRIGGER IF NOT EXISTS liquidaciones_valores_inmutables
BEFORE UPDATE OF kilos, humedad, factor_rendimiento, precio_kg, lineas, neto, parametros
ON liquidaciones
BEGIN
    SELECT RAISE(ABORT, 'Los valores de una liquidacion no se modifican (RN-10)');
END;
"""


def inicializar(ruta: Path) -> None:
    """Crea el archivo y el esquema si no existen. Es idempotente."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("PRAGMA journal_mode = WAL")
        conexion.executescript(ESQUEMA)


class UnidadDeTrabajo:
    """Una transacción con sus repositorios. Confirma al salir o revierte si hubo error.

    Uso desde la capa de negocio::

        with fabrica_uow() as uow:
            fila = uow.productores.buscar_por_cedula("1075123456")
            uow.liquidaciones.insertar({...})
        # aquí ya se hizo COMMIT; si algo falló adentro, ROLLBACK
    """

    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        self._conexion: sqlite3.Connection | None = None

    def __enter__(self) -> UnidadDeTrabajo:
        # isolation_level=None desactiva las transacciones implícitas de sqlite3
        # para que el inicio y el fin los marque esta clase y nadie más.
        conexion = sqlite3.connect(self._ruta, isolation_level=None)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.execute("BEGIN IMMEDIATE")
        self._conexion = conexion
        self.productores = RepositorioProductores(conexion)
        self.precios = RepositorioPrecios(conexion)
        self.liquidaciones = RepositorioLiquidaciones(conexion)
        self.auditoria = RepositorioAuditoria(conexion)
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        assert self._conexion is not None
        try:
            self._conexion.execute("COMMIT" if tipo is None else "ROLLBACK")
        finally:
            self._conexion.close()
            self._conexion = None
