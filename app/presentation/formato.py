"""Formato colombiano para las vistas: punto de miles y coma decimal."""

from __future__ import annotations

from decimal import Decimal


def pesos(valor: int) -> str:
    """2305500 -> '$ 2.305.500'; -22200 -> '-$ 22.200'."""
    signo = "-" if valor < 0 else ""
    return f"{signo}$ {abs(valor):,}".replace(",", ".")


def numero(valor: Decimal | int | float, decimales: int = 1) -> str:
    """190.3 -> '190,3'; 1234.5 -> '1.234,5'."""
    texto = f"{Decimal(valor):,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")
