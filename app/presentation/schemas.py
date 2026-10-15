"""Esquemas de entrada y salida de la API (Pydantic).

Aquí solo se valida el formato: que la humedad sea un número entre 0 y 100,
por ejemplo. Si está entre 10 y 12 lo decide el dominio, porque es una regla
de negocio que puede cambiar y no debe quedar repetida en dos capas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.business.domain.models import (
    DefectoTaza,
    Liquidacion,
    PrecioDelDia,
    Productor,
)
from app.business.domain.reportes import ReporteDiario


class ProductorEntrada(BaseModel):
    cedula: str = Field(min_length=5, max_length=13, examples=["1075123456"])
    nombre: str = Field(min_length=3, max_length=120)
    vereda: str = Field(min_length=2, max_length=80)
    telefono: str | None = Field(default=None, max_length=20)
    programa_especial: bool = False
    acepta_tratamiento_datos: bool = Field(description="Autorización previa, expresa e informada (Ley 1581)")


class ProductorSalida(BaseModel):
    id: int
    cedula: str = Field(description="Enmascarada: solo los últimos 4 dígitos")
    nombre: str
    vereda: str
    programa_especial: bool
    fecha_autorizacion_datos: date

    @classmethod
    def desde(cls, productor: Productor) -> ProductorSalida:
        return cls(
            id=productor.id or 0,
            cedula=productor.cedula.enmascarada(),
            nombre=productor.nombre,
            vereda=productor.vereda,
            programa_especial=productor.programa_especial,
            fecha_autorizacion_datos=productor.fecha_autorizacion_datos,
        )


class PrecioEntrada(BaseModel):
    fecha: date
    precio_carga_fr94: int = Field(gt=0, examples=[2_220_000])
    precio_pasilla_kg: int = Field(gt=0, examples=[10_000])


class PrecioSalida(PrecioEntrada):
    @classmethod
    def desde(cls, precio: PrecioDelDia) -> PrecioSalida:
        return cls(
            fecha=precio.fecha,
            precio_carga_fr94=precio.precio_carga_fr94,
            precio_pasilla_kg=precio.precio_pasilla_kg,
        )


class EntregaEntrada(BaseModel):
    cedula: str = Field(min_length=5, max_length=13)
    kilos: Decimal = Field(gt=0, le=20_000, decimal_places=1, examples=["190.5"])
    humedad: Decimal = Field(ge=0, le=100, decimal_places=1, examples=["11.2"])
    factor_rendimiento: Decimal = Field(gt=0, le=200, decimal_places=1, examples=["92.4"])
    defecto: DefectoTaza = DefectoTaza.NINGUNO


class HistorialEntrada(BaseModel):
    """La cédula va en el cuerpo y no en la URL: las URL quedan en los registros (QA-04)."""

    cedula: str = Field(min_length=5, max_length=13)


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)
    responsable: str = Field(min_length=3, max_length=80)


class PagoEntrada(BaseModel):
    responsable: str = Field(min_length=3, max_length=80)


class LineaSalida(BaseModel):
    concepto: str
    valor: int


class ResumenProductor(BaseModel):
    cedula: str
    nombre: str
    vereda: str


class LiquidacionSalida(BaseModel):
    id: int
    fecha: date
    estado: str
    productor: ResumenProductor
    kilos: Decimal
    arrobas: Decimal
    cargas: Decimal
    humedad: Decimal
    factor_rendimiento: Decimal
    defecto: DefectoTaza
    precio_kg: int
    lineas: list[LineaSalida]
    neto: int
    motivo_anulacion: str | None = None

    @classmethod
    def desde(cls, liq: Liquidacion) -> LiquidacionSalida:
        entrega = liq.entrega
        return cls(
            id=liq.id or 0,
            fecha=entrega.fecha,
            estado=liq.estado.value,
            productor=ResumenProductor(
                cedula=entrega.productor.cedula.enmascarada(),
                nombre=entrega.productor.nombre,
                vereda=entrega.productor.vereda,
            ),
            kilos=entrega.kilos,
            arrobas=entrega.arrobas.quantize(Decimal("0.01")),
            cargas=entrega.cargas.quantize(Decimal("0.001")),
            humedad=entrega.humedad,
            factor_rendimiento=entrega.factor_rendimiento,
            defecto=entrega.defecto,
            precio_kg=liq.precio_kg,
            lineas=[LineaSalida(concepto=l.concepto, valor=l.valor) for l in liq.lineas],
            neto=liq.neto,
            motivo_anulacion=liq.motivo_anulacion,
        )


class ReporteSalida(BaseModel):
    fecha: date
    entregas: int
    anuladas: int
    kilos: Decimal
    cargas: Decimal
    valor_neto: int
    fr_promedio_ponderado: Decimal | None

    @classmethod
    def desde(cls, reporte: ReporteDiario) -> ReporteSalida:
        return cls(
            fecha=reporte.fecha,
            entregas=reporte.entregas,
            anuladas=reporte.anuladas,
            kilos=reporte.kilos,
            cargas=reporte.cargas.quantize(Decimal("0.01")),
            valor_neto=reporte.valor_neto,
            fr_promedio_ponderado=reporte.fr_promedio_ponderado,
        )


class ErrorSalida(BaseModel):
    detalle: str
