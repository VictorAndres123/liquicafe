"""Reglas de dinero de la liquidación (RN-06 a RN-08).

Cada regla es una clase pequeña que recibe el contexto y devuelve, como
mucho, una línea del desglose. El ``Liquidador`` las aplica en orden y cada
una ve el subtotal que dejaron las anteriores, parecido a una cadena de
filtros. Agregar una bonificación nueva es escribir una clase y añadirla a la
lista: no se toca ninguna otra capa (escenario QA-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Mapping, Protocol

from app.business.domain.models import DefectoTaza, Entrega, LineaLiquidacion

_UN_PESO = Decimal("1")


def a_pesos(valor: Decimal) -> int:
    """Redondea al peso. Se usa ``Decimal`` porque con ``float`` 0,1 + 0,2 no da 0,3."""
    return int(valor.quantize(_UN_PESO, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class ContextoLiquidacion:
    entrega: Entrega
    precio_kg: int
    subtotal: int


class Ajuste(Protocol):
    """Contrato común de las reglas. ``None`` significa que la regla no aplica."""

    def aplicar(self, contexto: ContextoLiquidacion) -> LineaLiquidacion | None: ...


@dataclass(frozen=True)
class ValorPorFactor:
    """Línea base: kilos entregados por precio por kilo según el FR."""

    def aplicar(self, contexto: ContextoLiquidacion) -> LineaLiquidacion:
        valor = contexto.entrega.kilos * contexto.precio_kg
        fr = contexto.entrega.factor_rendimiento
        return LineaLiquidacion(f"Café pergamino seco, FR {fr}", a_pesos(valor))


@dataclass(frozen=True)
class DescuentoPorTaza:
    """Descuento por carga según el defecto de taza (valores de la FNC)."""

    valores_por_carga: Mapping[DefectoTaza, int]

    def aplicar(self, contexto: ContextoLiquidacion) -> LineaLiquidacion | None:
        defecto = contexto.entrega.defecto
        if defecto is DefectoTaza.NINGUNO:
            return None
        valor = self.valores_por_carga[defecto] * contexto.entrega.cargas
        return LineaLiquidacion(f"Descuento por taza: {defecto.etiqueta}", -a_pesos(valor))


@dataclass(frozen=True)
class BonificacionProgramaEspecial:
    """Bonificación por carga para asociados de un programa de cafés especiales."""

    valor_por_carga: int

    def aplicar(self, contexto: ContextoLiquidacion) -> LineaLiquidacion | None:
        if not contexto.entrega.productor.programa_especial:
            return None
        valor = self.valor_por_carga * contexto.entrega.cargas
        return LineaLiquidacion("Bonificación programa de cafés especiales", a_pesos(valor))


@dataclass(frozen=True)
class CuotaSostenimiento:
    """Porcentaje del subtotal que retiene la asociación. Va de último a propósito."""

    porcentaje: Decimal

    def aplicar(self, contexto: ContextoLiquidacion) -> LineaLiquidacion | None:
        if self.porcentaje == 0:
            return None
        valor = Decimal(contexto.subtotal) * self.porcentaje / 100
        return LineaLiquidacion(f"Cuota de sostenimiento ({self.porcentaje} %)", -a_pesos(valor))
