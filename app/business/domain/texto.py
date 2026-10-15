"""Números escritos como se escriben en Colombia: coma decimal y punto de miles.

Vive en el dominio porque los mensajes de rechazo y los conceptos del
desglose son parte del lenguaje del negocio: el recibidor se los lee tal
cual al asociado ("humedad de 13,4 %"), no son un detalle de la vista.
"""

from __future__ import annotations

from decimal import Decimal


def decimal_es(valor: Decimal | int, decimales: int | None = None) -> str:
    """13.4 -> '13,4'; 1.0 -> '1'; 1234.5 -> '1.234,5'."""
    numero = Decimal(valor)
    if decimales is None:
        numero = numero.normalize()
        decimales = max(0, -numero.as_tuple().exponent)
    texto = f"{numero:,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def pesos_es(valor: int) -> str:
    """2305500 -> '$ 2.305.500'; -22200 -> '-$ 22.200'."""
    signo = "-" if valor < 0 else ""
    return f"{signo}$ {decimal_es(abs(valor), 0)}"
