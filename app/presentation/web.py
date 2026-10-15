"""Vistas HTML para la bodega (el "controlador" y la "vista" de un MVC local).

MVC vive aquí adentro de la capa de presentación: estas funciones son los
controladores, las plantillas Jinja2 son las vistas y el "modelo" es la
capa de negocio completa. Ningún controlador toca la base de datos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.business.domain.errores import ErrorDeNegocio
from app.business.domain.models import DefectoTaza
from app.presentation.dependencias import ServiciosDep
from app.presentation.errores import ErrorDeFormulario, estado_http
from app.presentation.plantillas import plantillas

router = APIRouter(include_in_schema=False)
Campo = Annotated[str, Form()]


def _decimal(texto: str, campo: str) -> Decimal:
    """Acepta coma o punto decimal, porque en la bodega se escribe '190,5'."""
    try:
        valor = Decimal(texto.strip().replace(",", "."))
    except InvalidOperation:
        raise ErrorDeFormulario(f"{campo}: escriba un número, por ejemplo 190,5.") from None
    if not valor.is_finite():
        raise ErrorDeFormulario(f"{campo}: escriba un número, por ejemplo 190,5.")
    return valor


def _pagina(request: Request, nombre: str, contexto: dict[str, Any], estado: int = 200) -> HTMLResponse:
    return plantillas.TemplateResponse(request, nombre, contexto, status_code=estado)


def _error(error: Exception) -> int:
    return estado_http(error) if isinstance(error, ErrorDeNegocio) else 422


@router.get("/")
def inicio() -> RedirectResponse:
    return RedirectResponse("/recibo", status_code=303)


@router.get("/recibo")
def recibo(request: Request, servicios: ServiciosDep) -> HTMLResponse:
    contexto = {"precio": servicios.precios.de_hoy(), "defectos": list(DefectoTaza), "datos": {}}
    return _pagina(request, "recibo.html", contexto)


@router.post("/recibo")
def recibir_entrega(
    request: Request,
    servicios: ServiciosDep,
    cedula: Campo,
    kilos: Campo,
    humedad: Campo,
    factor_rendimiento: Campo,
    defecto: Annotated[DefectoTaza, Form()] = DefectoTaza.NINGUNO,
) -> Response:
    datos = {"cedula": cedula, "kilos": kilos, "humedad": humedad, "factor_rendimiento": factor_rendimiento, "defecto": defecto}
    try:
        liquidacion = servicios.entregas.registrar_y_liquidar(
            cedula=cedula,
            kilos=_decimal(kilos, "Peso"),
            humedad=_decimal(humedad, "Humedad"),
            factor_rendimiento=_decimal(factor_rendimiento, "Factor de rendimiento"),
            defecto=defecto,
        )
    except (ErrorDeNegocio, ErrorDeFormulario) as error:
        contexto = {"precio": servicios.precios.de_hoy(), "defectos": list(DefectoTaza), "datos": datos, "error": str(error)}
        return _pagina(request, "recibo.html", contexto, _error(error))
    return RedirectResponse(f"/liquidaciones/{liquidacion.id}", status_code=303)


@router.get("/liquidaciones/{id_}")
def comprobante(request: Request, id_: int, servicios: ServiciosDep, error: str | None = None) -> HTMLResponse:
    contexto = {
        "liq": servicios.entregas.obtener(id_),
        "auditoria": servicios.entregas.auditoria(id_),
        "error": error,
    }
    return _pagina(request, "comprobante.html", contexto)


@router.post("/liquidaciones/{id_}/anular")
def anular(request: Request, id_: int, servicios: ServiciosDep, motivo: Campo, responsable: Campo) -> Response:
    try:
        servicios.entregas.anular(id_, motivo=motivo, responsable=responsable)
    except ErrorDeNegocio as error:
        contexto = {"liq": servicios.entregas.obtener(id_), "auditoria": servicios.entregas.auditoria(id_), "error": str(error)}
        return _pagina(request, "comprobante.html", contexto, _error(error))
    return RedirectResponse(f"/liquidaciones/{id_}", status_code=303)


@router.post("/liquidaciones/{id_}/pagar")
def pagar(request: Request, id_: int, servicios: ServiciosDep, responsable: Campo) -> Response:
    try:
        servicios.entregas.marcar_pagada(id_, responsable=responsable)
    except ErrorDeNegocio as error:
        contexto = {"liq": servicios.entregas.obtener(id_), "auditoria": servicios.entregas.auditoria(id_), "error": str(error)}
        return _pagina(request, "comprobante.html", contexto, _error(error))
    return RedirectResponse(f"/liquidaciones/{id_}", status_code=303)


@router.get("/productores")
def productores(request: Request, servicios: ServiciosDep) -> HTMLResponse:
    return _pagina(request, "productores.html", {"productores": servicios.productores.listar(), "datos": {}})


@router.post("/productores")
def registrar_productor(
    request: Request,
    servicios: ServiciosDep,
    cedula: Campo,
    nombre: Campo,
    vereda: Campo,
    telefono: Annotated[str, Form()] = "",
    programa_especial: Annotated[bool, Form()] = False,
    acepta_tratamiento_datos: Annotated[bool, Form()] = False,
) -> Response:
    try:
        servicios.productores.registrar(
            cedula=cedula,
            nombre=nombre,
            vereda=vereda,
            telefono=telefono,
            programa_especial=programa_especial,
            acepta_tratamiento_datos=acepta_tratamiento_datos,
        )
    except ErrorDeNegocio as error:
        datos = {"cedula": cedula, "nombre": nombre, "vereda": vereda, "telefono": telefono, "programa_especial": programa_especial}
        contexto = {"productores": servicios.productores.listar(), "datos": datos, "error": str(error)}
        return _pagina(request, "productores.html", contexto, _error(error))
    return RedirectResponse("/productores", status_code=303)


@router.get("/historial")
def formulario_historial(request: Request) -> HTMLResponse:
    return _pagina(request, "historial.html", {"liquidaciones": None})


@router.post("/historial")
def historial(request: Request, servicios: ServiciosDep, cedula: Campo) -> HTMLResponse:
    # POST y no GET: así la cédula no queda en la URL ni en el historial del navegador.
    try:
        productor = servicios.productores.obtener(cedula)
        liquidaciones = servicios.entregas.historial(cedula)
    except ErrorDeNegocio as error:
        return _pagina(request, "historial.html", {"liquidaciones": None, "error": str(error)}, _error(error))
    return _pagina(request, "historial.html", {"productor": productor, "liquidaciones": liquidaciones})


@router.get("/precio")
def precio(request: Request, servicios: ServiciosDep) -> HTMLResponse:
    return _pagina(request, "precio.html", {"precio": servicios.precios.de_hoy(), "hoy": servicios.precios.fecha_de_hoy()})


@router.post("/precio")
def registrar_precio(
    request: Request,
    servicios: ServiciosDep,
    fecha: Annotated[date, Form()],
    precio_carga_fr94: Annotated[int, Form()],
    precio_pasilla_kg: Annotated[int, Form()],
) -> Response:
    try:
        servicios.precios.registrar(fecha=fecha, precio_carga_fr94=precio_carga_fr94, precio_pasilla_kg=precio_pasilla_kg)
    except ErrorDeNegocio as error:
        contexto = {"precio": servicios.precios.de_hoy(), "hoy": fecha, "error": str(error)}
        return _pagina(request, "precio.html", contexto, _error(error))
    return RedirectResponse("/recibo", status_code=303)


@router.get("/reporte")
def reporte(request: Request, servicios: ServiciosDep, fecha: date | None = None) -> HTMLResponse:
    dia = fecha or servicios.precios.fecha_de_hoy()
    return _pagina(request, "reporte.html", {"reporte": servicios.reportes.diario(dia)})
