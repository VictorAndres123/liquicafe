"""Lectura de los parámetros de liquidación desde un archivo JSON.

Leer archivos es entrada/salida, así que vive en esta capa y no en el
dominio. Se devuelve un diccionario plano: la capa de negocio decide qué
hacer con él (``Liquidador.desde_parametros``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLAVES_OBLIGATORIAS = {
    "fuente_tabla",
    "kg_pasilla_por_carga",
    "humedad_minima",
    "humedad_maxima",
    "descuentos_taza_por_carga",
    "bonificacion_programa_por_carga",
    "cuota_sostenimiento_porcentaje",
}


def cargar_parametros(ruta: Path) -> dict[str, Any]:
    """Falla al arrancar, y no en plena cosecha, si al archivo le falta algo."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    faltantes = CLAVES_OBLIGATORIAS - datos.keys()
    if faltantes:
        raise ValueError(f"Faltan parámetros en {ruta.name}: {', '.join(sorted(faltantes))}")
    return datos
