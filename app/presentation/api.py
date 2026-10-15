"""API REST en JSON (documentada en /docs con Swagger).

Cada ruta hace tres cosas y nada más: recibe un esquema validado, llama un
servicio de negocio y convierte el resultado en un esquema de salida.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, status

from app.presentation.dependencias import ServiciosDep
from app.presentation.schemas import (
    AnulacionEntrada,
    EntregaEntrada,
    ErrorSalida,
    HistorialEntrada,
    LiquidacionSalida,
    PagoEntrada,
    PrecioEntrada,
    PrecioSalida,
    ProductorEntrada,
    ProductorSalida,
    ReporteSalida,
)

ERRORES = {
    404: {"model": ErrorSalida, "description": "No existe"},
    409: {"model": ErrorSalida, "description": "Ya existe"},
    422: {"model": ErrorSalida, "description": "Regla de negocio no cumplida"},
}

router = APIRouter(prefix="/api", responses=ERRORES)


@router.post("/productores", status_code=status.HTTP_201_CREATED, tags=["Asociados"])
def registrar_productor(datos: ProductorEntrada, servicios: ServiciosDep) -> ProductorSalida:
    return ProductorSalida.desde(servicios.productores.registrar(**datos.model_dump()))


@router.get("/productores", tags=["Asociados"])
def listar_productores(servicios: ServiciosDep) -> list[ProductorSalida]:
    return [ProductorSalida.desde(p) for p in servicios.productores.listar()]


@router.post("/precios", status_code=status.HTTP_201_CREATED, tags=["Precio del día"])
def registrar_precio(datos: PrecioEntrada, servicios: ServiciosDep) -> PrecioSalida:
    return PrecioSalida.desde(servicios.precios.registrar(**datos.model_dump()))


@router.get("/precios/{fecha}", tags=["Precio del día"])
def obtener_precio(fecha: date, servicios: ServiciosDep) -> PrecioSalida | None:
    precio = servicios.precios.obtener(fecha)
    return PrecioSalida.desde(precio) if precio else None


@router.post("/liquidaciones", status_code=status.HTTP_201_CREATED, tags=["Liquidaciones"])
def liquidar_entrega(datos: EntregaEntrada, servicios: ServiciosDep) -> LiquidacionSalida:
    liquidacion = servicios.entregas.registrar_y_liquidar(**datos.model_dump(), responsable="API")
    return LiquidacionSalida.desde(liquidacion)


@router.get("/liquidaciones/{id_}", tags=["Liquidaciones"])
def obtener_liquidacion(id_: int, servicios: ServiciosDep) -> LiquidacionSalida:
    return LiquidacionSalida.desde(servicios.entregas.obtener(id_))


@router.post("/liquidaciones/{id_}/anulacion", tags=["Liquidaciones"])
def anular_liquidacion(id_: int, datos: AnulacionEntrada, servicios: ServiciosDep) -> LiquidacionSalida:
    return LiquidacionSalida.desde(servicios.entregas.anular(id_, **datos.model_dump()))


@router.post("/liquidaciones/{id_}/pago", tags=["Liquidaciones"])
def pagar_liquidacion(id_: int, datos: PagoEntrada, servicios: ServiciosDep) -> LiquidacionSalida:
    return LiquidacionSalida.desde(servicios.entregas.marcar_pagada(id_, **datos.model_dump()))


@router.post("/historial", tags=["Liquidaciones"])
def historial(datos: HistorialEntrada, servicios: ServiciosDep) -> list[LiquidacionSalida]:
    return [LiquidacionSalida.desde(liq) for liq in servicios.entregas.historial(datos.cedula)]


@router.get("/reportes/diario", tags=["Reportes"])
def reporte_diario(fecha: date, servicios: ServiciosDep) -> ReporteSalida:
    return ReporteSalida.desde(servicios.reportes.diario(fecha))
