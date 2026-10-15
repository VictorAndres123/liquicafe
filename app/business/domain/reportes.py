"""Reporte diario de compras para tesorería (RF-09)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from app.business.domain.models import KG_POR_CARGA, EstadoLiquidacion, Liquidacion


@dataclass(frozen=True)
class ReporteDiario:
    fecha: date
    entregas: int
    anuladas: int
    kilos: Decimal
    valor_neto: int
    fr_promedio_ponderado: Decimal | None

    @property
    def cargas(self) -> Decimal:
        return self.kilos / KG_POR_CARGA

    @classmethod
    def desde(cls, fecha: date, liquidaciones: Iterable[Liquidacion]) -> ReporteDiario:
        """Excluye las anuladas y pondera el FR por kilos.

        Un promedio simple engañaría: una entrega de 20 kg con FR 99 pesaría
        lo mismo que una de 500 kg con FR 90.
        """
        todas = list(liquidaciones)
        validas = [liq for liq in todas if liq.estado is not EstadoLiquidacion.ANULADA]
        kilos = sum((liq.entrega.kilos for liq in validas), Decimal("0"))
        fr_ponderado = None
        if kilos > 0:
            suma = sum(liq.entrega.kilos * liq.entrega.factor_rendimiento for liq in validas)
            fr_ponderado = (suma / kilos).quantize(Decimal("0.01"))
        return cls(
            fecha=fecha,
            entregas=len(validas),
            anuladas=len(todas) - len(validas),
            kilos=kilos,
            valor_neto=sum(liq.neto for liq in validas),
            fr_promedio_ponderado=fr_ponderado,
        )
