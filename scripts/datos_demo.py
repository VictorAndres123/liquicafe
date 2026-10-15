"""Carga datos de demostración para probar LiquiCafé en un minuto.

Registra el precio de hoy con los valores del boletín FNC del 9 de abril de
2026 y tres asociados ficticios. Se puede ejecutar varias veces: lo que ya
existe se omite.

    python -m scripts.datos_demo
"""

from __future__ import annotations

from datetime import date

from app.business.domain.errores import Conflicto
from app.main import crear_app

ASOCIADOS = [
    {"cedula": "1075123456", "nombre": "Luz Dary Muñoz", "vereda": "Bruselas", "programa_especial": True},
    {"cedula": "12345678", "nombre": "Jorge Eliécer Cuéllar", "vereda": "Charguayaco", "programa_especial": False},
    {"cedula": "36123987", "nombre": "María Ofelia Rojas", "vereda": "Criollo", "programa_especial": False},
]


def main() -> None:
    servicios = crear_app().state.servicios
    try:
        servicios.precios.registrar(fecha=date.today(), precio_carga_fr94=2_220_000, precio_pasilla_kg=10_000)
        print("Precio de hoy registrado: carga FR 94 a $2.220.000, pasilla a $10.000/kg")
    except Conflicto:
        print("Ya había precio para hoy; se deja como está.")
    for asociado in ASOCIADOS:
        try:
            servicios.productores.registrar(**asociado, acepta_tratamiento_datos=True)
            print(f"Asociado registrado: {asociado['nombre']}")
        except Conflicto:
            print(f"Ya existía: {asociado['nombre']}")


if __name__ == "__main__":
    main()
