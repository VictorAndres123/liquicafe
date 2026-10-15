"""Fixtures compartidas.

Las pruebas usan los parámetros reales de ``config/parametros.json`` y el
precio que la FNC publicó el 9 de abril de 2026, para que el oráculo sea un
dato oficial y no un número inventado.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.business.domain.liquidador import Liquidador
from app.business.domain.models import Cedula, Entrega, PrecioDelDia, Productor

RAIZ = Path(__file__).resolve().parents[1]
RUTA_PARAMETROS = RAIZ / "config" / "parametros.json"
DIA_FNC = date(2026, 4, 9)


@pytest.fixture
def parametros() -> dict:
    return json.loads(RUTA_PARAMETROS.read_text(encoding="utf-8"))


@pytest.fixture
def liquidador(parametros) -> Liquidador:
    return Liquidador.desde_parametros(parametros)


@pytest.fixture
def precio_fnc() -> PrecioDelDia:
    """Boletín FNC del 9 de abril de 2026: carga FR 94 a $2.220.000, pasilla a $10.000/kg."""
    return PrecioDelDia(fecha=DIA_FNC, precio_carga_fr94=2_220_000, precio_pasilla_kg=10_000)


@pytest.fixture
def productor() -> Productor:
    return Productor(
        cedula=Cedula("1075123456"),
        nombre="Luz Dary Muñoz",
        vereda="Bruselas",
        fecha_autorizacion_datos=DIA_FNC,
        id=1,
    )


@pytest.fixture
def nueva_entrega(productor):
    """Fábrica de entregas con valores por defecto válidos."""

    def _crear(**cambios) -> Entrega:
        datos = dict(
            productor=productor,
            fecha=DIA_FNC,
            kilos=Decimal("125"),
            humedad=Decimal("11.0"),
            factor_rendimiento=Decimal("94"),
        )
        datos.update(cambios)
        return Entrega(**datos)

    return _crear
