"""Filtros de Jinja2 con formato colombiano (punto de miles y coma decimal).

Reutiliza las funciones del dominio para que el comprobante y los mensajes
de rechazo escriban los números exactamente igual.
"""

from __future__ import annotations

from decimal import Decimal

from app.business.domain.texto import decimal_es, pesos_es


def pesos(valor: int) -> str:
    return pesos_es(valor)


def numero(valor: Decimal | int, decimales: int = 1) -> str:
    return decimal_es(valor, decimales)
