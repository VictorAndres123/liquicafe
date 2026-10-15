"""Repositorios: SQL de cada tabla, con entrada y salida en diccionarios.

Decisión de diseño: los repositorios no conocen las clases del dominio. Si
devolvieran ``Productor`` o ``Liquidacion``, esta capa tendría que importar
``app.business`` y la dependencia apuntaría hacia arriba, contra el patrón.
El costo es que la capa de negocio hace el mapeo (``app.business.mapeo``).
"""

from __future__ import annotations

import sqlite3
from typing import Any

Fila = dict[str, Any]


def _a_dict(fila: sqlite3.Row | None) -> Fila | None:
    return dict(fila) if fila is not None else None


class RepositorioProductores:
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._db = conexion

    def insertar(self, fila: Fila) -> int:
        cursor = self._db.execute(
            """INSERT INTO productores
               (cedula, nombre, vereda, telefono, programa_especial, fecha_autorizacion_datos)
               VALUES (:cedula, :nombre, :vereda, :telefono, :programa_especial, :fecha_autorizacion_datos)""",
            fila,
        )
        return int(cursor.lastrowid)

    def buscar_por_cedula(self, cedula: str) -> Fila | None:
        return _a_dict(self._db.execute("SELECT * FROM productores WHERE cedula = ?", (cedula,)).fetchone())

    def listar(self) -> list[Fila]:
        return [dict(f) for f in self._db.execute("SELECT * FROM productores ORDER BY nombre")]


class RepositorioPrecios:
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._db = conexion

    def insertar(self, fila: Fila) -> None:
        self._db.execute(
            "INSERT INTO precios (fecha, precio_carga_fr94, precio_pasilla_kg) "
            "VALUES (:fecha, :precio_carga_fr94, :precio_pasilla_kg)",
            fila,
        )

    def obtener(self, fecha: str) -> Fila | None:
        return _a_dict(self._db.execute("SELECT * FROM precios WHERE fecha = ?", (fecha,)).fetchone())


class RepositorioLiquidaciones:
    # Cada liquidación se devuelve junto con los datos de su productor, porque
    # en el dominio una Entrega siempre sabe de quién es.
    _SELECT = """
        SELECT l.*,
               p.cedula AS p_cedula, p.nombre AS p_nombre, p.vereda AS p_vereda,
               p.telefono AS p_telefono, p.programa_especial AS p_programa_especial,
               p.fecha_autorizacion_datos AS p_fecha_autorizacion_datos
        FROM liquidaciones l JOIN productores p ON p.id = l.productor_id
    """

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._db = conexion

    def insertar(self, fila: Fila) -> int:
        cursor = self._db.execute(
            """INSERT INTO liquidaciones
               (productor_id, fecha, kilos, humedad, factor_rendimiento, defecto,
                precio_kg, lineas, neto, parametros, estado)
               VALUES (:productor_id, :fecha, :kilos, :humedad, :factor_rendimiento, :defecto,
                       :precio_kg, :lineas, :neto, :parametros, :estado)""",
            fila,
        )
        return int(cursor.lastrowid)

    def obtener(self, id_: int) -> Fila | None:
        return _a_dict(self._db.execute(self._SELECT + " WHERE l.id = ?", (id_,)).fetchone())

    def listar_por_productor(self, productor_id: int) -> list[Fila]:
        sql = self._SELECT + " WHERE l.productor_id = ? ORDER BY l.fecha DESC, l.id DESC"
        return [dict(f) for f in self._db.execute(sql, (productor_id,))]

    def listar_por_fecha(self, fecha: str) -> list[Fila]:
        return [dict(f) for f in self._db.execute(self._SELECT + " WHERE l.fecha = ? ORDER BY l.id", (fecha,))]

    def actualizar_estado(
        self, id_: int, estado: str, motivo: str | None = None, responsable: str | None = None
    ) -> None:
        # Solo cambian columnas de estado; los valores de dinero los protege un trigger.
        self._db.execute(
            "UPDATE liquidaciones SET estado = ?, motivo_anulacion = ?, responsable_anulacion = ? WHERE id = ?",
            (estado, motivo, responsable, id_),
        )


class RepositorioAuditoria:
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._db = conexion

    def registrar(self, fila: Fila) -> None:
        self._db.execute(
            "INSERT INTO auditoria (liquidacion_id, evento, detalle, responsable, momento) "
            "VALUES (:liquidacion_id, :evento, :detalle, :responsable, :momento)",
            fila,
        )

    def listar(self, liquidacion_id: int) -> list[Fila]:
        sql = "SELECT * FROM auditoria WHERE liquidacion_id = ? ORDER BY id"
        return [dict(f) for f in self._db.execute(sql, (liquidacion_id,))]
