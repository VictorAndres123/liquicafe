"""La tabla de precios por FR se valida contra el boletín oficial de la FNC."""

from __future__ import annotations

from decimal import Decimal

import pytest

# (FR, precio total por carga publicado por la FNC el 9 de abril de 2026)
TABLA_FNC_2026_04_09 = [
    (88, 2_305_500),
    (89, 2_300_500),
    (90, 2_282_875),
    (91, 2_264_375),
    (92, 2_249_375),
    (93, 2_233_250),
    (94, 2_220_000),
    (95, 2_205_125),
    (96, 2_189_750),
    (97, 2_177_375),
    (98, 2_163_625),
    (99, 2_152_000),
    (100, 2_138_125),
]


TOLERANCIA_PESOS_POR_KG = 1
"""Por qué 1 peso y no 0: la primera versión exigía igualdad exacta y fallaron
4 de 13 FR (95, 96, 97 y 100), siempre por un peso por kilo. Busqué un precio
del excelso que reprodujera las 13 filas a la vez, redondeando y truncando, y
no existe: la FNC redondea con datos internos que no publica. Un peso por kilo
son $125 por carga, menos del 0,006 % del precio."""


@pytest.mark.parametrize(("fr", "precio_carga_fnc"), TABLA_FNC_2026_04_09)
def test_precio_por_kilo_coincide_con_la_fnc(liquidador, precio_fnc, fr, precio_carga_fnc):
    precio_kg_fnc = precio_carga_fnc // 125
    calculado = liquidador.tabla.precio_kg(Decimal(fr), precio_fnc)
    assert abs(calculado - precio_kg_fnc) <= TOLERANCIA_PESOS_POR_KG


def test_el_fr_base_reproduce_exactamente_el_precio_publicado(liquidador, precio_fnc):
    assert liquidador.tabla.precio_kg(Decimal(94), precio_fnc) * 125 == 2_220_000


def test_kilos_de_excelso_por_carga_siguen_la_definicion_del_factor(liquidador):
    # 125 kg de pergamino con FR 88 rinden 99,43 kg de excelso (dato FNC).
    assert liquidador.tabla.kg_excelso_por_carga(Decimal(88)).quantize(Decimal("0.01")) == Decimal("99.43")


def test_la_regla_proporcional_no_sirve_con_fr_bajo(liquidador, precio_fnc):
    """Regresión del hallazgo del diagnóstico: 94/FR paga 2,86 % de más con FR 88."""
    proporcional = Decimal(2_220_000) * 94 / 88 / 125
    calculado = liquidador.tabla.precio_kg(Decimal(88), precio_fnc)
    assert calculado == 18_444
    assert proporcional > calculado * Decimal("1.028")


def test_fr_con_decimal_se_interpola_entre_filas(liquidador, precio_fnc):
    tabla = liquidador.tabla
    assert tabla.kg_pasilla_por_carga(Decimal("91.5")) == Decimal("6.000")
    precio = tabla.precio_kg(Decimal("91.5"), precio_fnc)
    assert tabla.precio_kg(Decimal(92), precio_fnc) < precio < tabla.precio_kg(Decimal(91), precio_fnc)


def test_fr_fuera_de_la_tabla_no_tiene_precio(liquidador, precio_fnc):
    with pytest.raises(ValueError):
        liquidador.tabla.precio_kg(Decimal("100.1"), precio_fnc)
