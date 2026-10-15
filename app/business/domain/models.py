"""Entidades y objetos de valor del dominio cafetero.

Todas las clases son inmutables (``frozen=True``). Una liquidación es un
soporte contable: si cambia de estado se crea una copia nueva con
``dataclasses.replace`` y la capa de negocio deja el rastro en la auditoría.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from app.business.domain.errores import DatoInvalido, TransicionNoPermitida

KG_POR_CARGA = Decimal("125")
"""Una carga de café pergamino seco son 125 kg (unidad del precio FNC)."""

KG_POR_ARROBA = Decimal("12.5")
"""En la bodega se habla en arrobas; el comprobante las muestra para el asociado."""


@dataclass(frozen=True)
class Cedula:
    """Número de cédula con enmascaramiento por defecto.

    ``str(cedula)`` devuelve la versión enmascarada a propósito: si alguien
    imprime una cédula en una plantilla sin pensarlo, sale protegida
    (escenario QA-04). El número completo solo se obtiene pidiendo ``numero``.
    """

    numero: str

    def __post_init__(self) -> None:
        limpio = self.numero.replace(".", "").replace(" ", "").strip()
        if not limpio.isdigit() or not 5 <= len(limpio) <= 10:
            raise DatoInvalido("La cédula debe tener entre 5 y 10 dígitos, sin letras.")
        object.__setattr__(self, "numero", limpio)

    def enmascarada(self) -> str:
        return "*" * (len(self.numero) - 4) + self.numero[-4:]

    def __str__(self) -> str:
        return self.enmascarada()


@dataclass(frozen=True)
class Productor:
    """Caficultor asociado. Solo existe si autorizó el tratamiento de sus datos."""

    cedula: Cedula
    nombre: str
    vereda: str
    fecha_autorizacion_datos: date
    telefono: str | None = None
    programa_especial: bool = False
    id: int | None = None


@dataclass(frozen=True)
class PrecioDelDia:
    """Precio publicado por la FNC que la gerencia registra cada mañana (RF-02)."""

    fecha: date
    precio_carga_fr94: int
    precio_pasilla_kg: int

    def __post_init__(self) -> None:
        if self.precio_carga_fr94 <= 0 or self.precio_pasilla_kg <= 0:
            raise DatoInvalido("Los precios deben ser mayores que cero.")


class DefectoTaza(str, Enum):
    """Defectos de la prueba de taza con descuento en la tabla de la FNC."""

    NINGUNO = "NINGUNO"
    TIPO_I = "TIPO_I"
    TIPO_II_LEVE = "TIPO_II_LEVE"
    TIPO_II_SEVERO = "TIPO_II_SEVERO"
    TIPO_III = "TIPO_III"

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS_DEFECTO[self]


_ETIQUETAS_DEFECTO = {
    DefectoTaza.NINGUNO: "Sin defecto",
    DefectoTaza.TIPO_I: "Tipo I (químico, fenol, moho)",
    DefectoTaza.TIPO_II_LEVE: "Tipo II, frecuencia 1/8 a 4/8 (fermento)",
    DefectoTaza.TIPO_II_SEVERO: "Tipo II, frecuencia 5/8 a 8/8 (fermento)",
    DefectoTaza.TIPO_III: "Tipo III (reposo)",
}


@dataclass(frozen=True)
class Entrega:
    """Café que un asociado trae a la bodega, con los datos medidos en la muestra."""

    productor: Productor
    fecha: date
    kilos: Decimal
    humedad: Decimal
    factor_rendimiento: Decimal
    defecto: DefectoTaza = DefectoTaza.NINGUNO

    @property
    def cargas(self) -> Decimal:
        return self.kilos / KG_POR_CARGA

    @property
    def arrobas(self) -> Decimal:
        return self.kilos / KG_POR_ARROBA


@dataclass(frozen=True)
class LineaLiquidacion:
    """Una línea del desglose. Positiva si suma al asociado, negativa si descuenta."""

    concepto: str
    valor: int


class EstadoLiquidacion(str, Enum):
    VIGENTE = "VIGENTE"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


@dataclass(frozen=True)
class Liquidacion:
    """Resultado de liquidar una entrega.

    ``parametros`` guarda una copia del precio del día y de las reglas que se
    aplicaron (RN-10). Si mañana cambia la bonificación, esta liquidación se
    sigue pudiendo explicar con los valores de su día (escenario QA-03).
    """

    entrega: Entrega
    precio_kg: int
    lineas: tuple[LineaLiquidacion, ...]
    parametros: Mapping[str, Any]
    estado: EstadoLiquidacion = EstadoLiquidacion.VIGENTE
    id: int | None = None
    motivo_anulacion: str | None = None
    responsable_anulacion: str | None = None

    @property
    def neto(self) -> int:
        return sum(linea.valor for linea in self.lineas)

    def anular(self, motivo: str, responsable: str) -> Liquidacion:
        """Anula sin borrar (RN-11). Una liquidación pagada ya salió de caja."""
        if self.estado is EstadoLiquidacion.PAGADA:
            raise TransicionNoPermitida(
                "La liquidación ya fue pagada; no se anula, se corrige con un ajuste contable."
            )
        if self.estado is EstadoLiquidacion.ANULADA:
            raise TransicionNoPermitida("La liquidación ya estaba anulada.")
        if not motivo.strip() or not responsable.strip():
            raise DatoInvalido("Para anular hay que indicar el motivo y quién anula.")
        return replace(
            self,
            estado=EstadoLiquidacion.ANULADA,
            motivo_anulacion=motivo.strip(),
            responsable_anulacion=responsable.strip(),
        )

    def marcar_pagada(self) -> Liquidacion:
        if self.estado is not EstadoLiquidacion.VIGENTE:
            raise TransicionNoPermitida(
                f"Solo se pagan liquidaciones vigentes; esta está {self.estado.value.lower()}."
            )
        return replace(self, estado=EstadoLiquidacion.PAGADA)


@dataclass(frozen=True)
class EventoAuditoria:
    """Rastro de lo que le pasó a una liquidación: quién, qué y cuándo (QA-03)."""

    evento: str
    detalle: str | None
    responsable: str
    momento: datetime
