"""Raíz de composición: el único módulo que conoce las tres capas.

Arma la aplicación de abajo hacia arriba: base de datos, parámetros,
liquidador, servicios y por último las rutas. Las capas no se construyen
entre sí, así que en las pruebas se puede cambiar la base de datos o el
reloj sin tocar ningún otro archivo.

Ejecución::

    uvicorn app.main:crear_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from fastapi import FastAPI

from app.business.domain.liquidador import Liquidador
from app.business.services import (
    Servicios,
    ServicioEntregas,
    ServicioPrecios,
    ServicioProductores,
    ServicioReportes,
)
from app.persistence import database
from app.persistence.configuracion import cargar_parametros
from app.presentation import api, errores, web

RAIZ = Path(__file__).resolve().parents[1]


def crear_app(
    ruta_bd: Path | None = None,
    ruta_parametros: Path | None = None,
    hoy: Callable[[], date] = date.today,
    ahora: Callable[[], datetime] = datetime.now,
) -> FastAPI:
    ruta_bd = Path(ruta_bd or os.environ.get("LIQUICAFE_DB", RAIZ / "datos" / "liquicafe.db"))
    ruta_parametros = Path(ruta_parametros or os.environ.get("LIQUICAFE_PARAMETROS", RAIZ / "config" / "parametros.json"))

    database.inicializar(ruta_bd)
    liquidador = Liquidador.desde_parametros(cargar_parametros(ruta_parametros))

    def unidad_de_trabajo() -> database.UnidadDeTrabajo:
        return database.UnidadDeTrabajo(ruta_bd)

    servicios = Servicios(
        productores=ServicioProductores(unidad_de_trabajo, hoy),
        precios=ServicioPrecios(unidad_de_trabajo, hoy),
        entregas=ServicioEntregas(unidad_de_trabajo, liquidador, hoy, ahora),
        reportes=ServicioReportes(unidad_de_trabajo),
    )

    app = FastAPI(
        title="LiquiCafé",
        version="0.1.0",
        description="Liquidación de compras de café pergamino seco. MVP con arquitectura en capas.",
    )
    app.state.servicios = servicios
    errores.registrar_manejadores(app)
    app.include_router(api.router)
    app.include_router(web.router)
    return app
