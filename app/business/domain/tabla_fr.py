"""Precio de compra según el factor de rendimiento (RN-01 a RN-03).

Por qué existe este módulo: la regla intuitiva, ``precio x 94 / FR``, se
aleja hasta un 2,86 % de la tabla oficial de la FNC (con FR 88 paga de más y
con FR 100 paga de menos). La razón es que la FNC paga aparte la pasilla que
trae el pergamino. El modelo que sí reproduce la tabla publicada es::

    precio_carga(FR) = kg_excelso(FR) * precio_excelso_kg + kg_pasilla(FR) * precio_pasilla_kg
    kg_excelso(FR)   = 125 * 70 / FR

El precio del excelso por kilo no se publica: se deduce del precio FR 94 que
la FNC sí publica cada día. La tabla de kilos de pasilla por FR es
configuración (``config/parametros.json``), no código, porque la FNC la puede
cambiar sin avisar.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Mapping

from app.business.domain.models import KG_POR_CARGA, PrecioDelDia

FR_BASE = Decimal("94")
KG_EXCELSO_POR_SACO = Decimal("70")
_UN_PESO = Decimal("1")


class TablaFactorRendimiento:
    """Kilos de pasilla por carga para cada FR entero publicado por la FNC."""

    def __init__(self, kg_pasilla_por_fr: Mapping[int, Decimal], fuente: str) -> None:
        if int(FR_BASE) not in kg_pasilla_por_fr:
            raise ValueError("La tabla debe incluir el FR base 94.")
        frs = sorted(kg_pasilla_por_fr)
        if frs != list(range(frs[0], frs[-1] + 1)):
            raise ValueError("La tabla debe tener todos los FR enteros del rango, sin huecos.")
        self._pasilla = {fr: Decimal(kg_pasilla_por_fr[fr]) for fr in frs}
        self.fuente = fuente
        self.fr_minimo = Decimal(frs[0])
        self.fr_maximo = Decimal(frs[-1])

    def admite(self, fr: Decimal) -> bool:
        return self.fr_minimo <= fr <= self.fr_maximo

    def kg_excelso_por_carga(self, fr: Decimal) -> Decimal:
        return KG_POR_CARGA * KG_EXCELSO_POR_SACO / fr

    def kg_pasilla_por_carga(self, fr: Decimal) -> Decimal:
        """Interpola entre los FR enteros de la tabla.

        La FNC publica FR enteros, pero en la bodega el FR de la muestra sale
        con un decimal (p. ej. 92,4). Interpolar es el supuesto S-10; con FR
        enteros el resultado es exactamente el valor publicado.
        """
        if not self.admite(fr):
            raise ValueError(f"FR {fr} fuera de la tabla ({self.fr_minimo} a {self.fr_maximo}).")
        inferior = int(fr)
        if Decimal(inferior) == fr:
            return self._pasilla[inferior]
        fraccion = fr - inferior
        return self._pasilla[inferior] + (self._pasilla[inferior + 1] - self._pasilla[inferior]) * fraccion

    def precio_kg(self, fr: Decimal, precio: PrecioDelDia) -> int:
        """Precio por kilo de pergamino para un FR, redondeado al peso.

        La FNC publica el precio por carga como un múltiplo exacto de 125:
        primero redondea el precio por kilo y luego multiplica. Por eso aquí
        también se redondea por kilo y no por carga.
        """
        precio_excelso_kg = (
            Decimal(precio.precio_carga_fr94)
            - self.kg_pasilla_por_carga(FR_BASE) * precio.precio_pasilla_kg
        ) / self.kg_excelso_por_carga(FR_BASE)
        precio_carga = (
            self.kg_excelso_por_carga(fr) * precio_excelso_kg
            + self.kg_pasilla_por_carga(fr) * precio.precio_pasilla_kg
        )
        return int((precio_carga / KG_POR_CARGA).quantize(_UN_PESO, rounding=ROUND_HALF_UP))
