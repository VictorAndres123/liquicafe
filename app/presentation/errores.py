"""Traducción de errores de negocio a respuestas HTTP.

El dominio no sabe de códigos HTTP; esta capa decide según la familia del
error. Las rutas ``/api`` reciben JSON y las vistas reciben una página.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.business.domain.errores import Conflicto, ErrorDeNegocio, NoEncontrado
from app.presentation.plantillas import plantillas


class ErrorDeFormulario(Exception):
    """Un campo del formulario HTML no tiene el formato esperado."""


def estado_http(error: ErrorDeNegocio) -> int:
    if isinstance(error, NoEncontrado):
        return 404
    if isinstance(error, Conflicto):
        return 409
    return 422


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDeNegocio)
    async def _error_de_negocio(request: Request, error: ErrorDeNegocio) -> Response:
        estado = estado_http(error)
        if request.url.path.startswith("/api"):
            return JSONResponse({"detalle": str(error)}, status_code=estado)
        return plantillas.TemplateResponse(request, "error.html", {"mensaje": str(error)}, status_code=estado)
