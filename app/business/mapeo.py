"""Traducción entre registros de persistencia (diccionarios) y objetos de dominio.

Este módulo es el precio de mantener las capas cerradas y la dependencia
hacia abajo: la persistencia no conoce el dominio, así que alguien de la
capa de negocio tiene que convertir en ambos sentidos.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.business.domain.models import (
    Cedula,
    DefectoTaza,
    Entrega,
    EstadoLiquidacion,
    EventoAuditoria,
    LineaLiquidacion,
    Liquidacion,
    PrecioDelDia,
    Productor,
)

Fila = dict[str, Any]


def fila_productor(productor: Productor) -> Fila:
    return {
        "cedula": productor.cedula.numero,
        "nombre": productor.nombre,
        "vereda": productor.vereda,
        "telefono": productor.telefono,
        "programa_especial": int(productor.programa_especial),
        "fecha_autorizacion_datos": productor.fecha_autorizacion_datos.isoformat(),
    }


def a_productor(fila: Fila, prefijo: str = "", id_: int | None = None) -> Productor:
    return Productor(
        cedula=Cedula(fila[f"{prefijo}cedula"]),
        nombre=fila[f"{prefijo}nombre"],
        vereda=fila[f"{prefijo}vereda"],
        telefono=fila[f"{prefijo}telefono"],
        programa_especial=bool(fila[f"{prefijo}programa_especial"]),
        fecha_autorizacion_datos=date.fromisoformat(fila[f"{prefijo}fecha_autorizacion_datos"]),
        id=id_ if id_ is not None else fila.get("id"),
    )


def fila_precio(precio: PrecioDelDia) -> Fila:
    return {
        "fecha": precio.fecha.isoformat(),
        "precio_carga_fr94": precio.precio_carga_fr94,
        "precio_pasilla_kg": precio.precio_pasilla_kg,
    }


def a_precio(fila: Fila) -> PrecioDelDia:
    return PrecioDelDia(
        fecha=date.fromisoformat(fila["fecha"]),
        precio_carga_fr94=fila["precio_carga_fr94"],
        precio_pasilla_kg=fila["precio_pasilla_kg"],
    )


def fila_liquidacion(liquidacion: Liquidacion) -> Fila:
    entrega = liquidacion.entrega
    return {
        "productor_id": entrega.productor.id,
        "fecha": entrega.fecha.isoformat(),
        "kilos": str(entrega.kilos),
        "humedad": str(entrega.humedad),
        "factor_rendimiento": str(entrega.factor_rendimiento),
        "defecto": entrega.defecto.value,
        "precio_kg": liquidacion.precio_kg,
        "lineas": json.dumps(
            [{"concepto": l.concepto, "valor": l.valor} for l in liquidacion.lineas], ensure_ascii=False
        ),
        "neto": liquidacion.neto,
        "parametros": json.dumps(liquidacion.parametros, ensure_ascii=False),
        "estado": liquidacion.estado.value,
    }


def a_liquidacion(fila: Fila) -> Liquidacion:
    productor = a_productor(fila, prefijo="p_", id_=fila["productor_id"])
    entrega = Entrega(
        productor=productor,
        fecha=date.fromisoformat(fila["fecha"]),
        kilos=Decimal(fila["kilos"]),
        humedad=Decimal(fila["humedad"]),
        factor_rendimiento=Decimal(fila["factor_rendimiento"]),
        defecto=DefectoTaza(fila["defecto"]),
    )
    return Liquidacion(
        entrega=entrega,
        precio_kg=fila["precio_kg"],
        lineas=tuple(LineaLiquidacion(**linea) for linea in json.loads(fila["lineas"])),
        parametros=json.loads(fila["parametros"]),
        estado=EstadoLiquidacion(fila["estado"]),
        id=fila["id"],
        motivo_anulacion=fila["motivo_anulacion"],
        responsable_anulacion=fila["responsable_anulacion"],
    )


def a_evento(fila: Fila) -> EventoAuditoria:
    return EventoAuditoria(
        evento=fila["evento"],
        detalle=fila["detalle"],
        responsable=fila["responsable"],
        momento=datetime.fromisoformat(fila["momento"]),
    )
