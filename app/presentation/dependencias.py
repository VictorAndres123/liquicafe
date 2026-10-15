"""Inyección de los servicios de negocio en las rutas.

Las rutas no construyen servicios ni conocen la base de datos: reciben la
fachada ``Servicios`` que armó ``app.main`` al arrancar.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.business.services import Servicios


def obtener_servicios(request: Request) -> Servicios:
    return request.app.state.servicios


ServiciosDep = Annotated[Servicios, Depends(obtener_servicios)]
