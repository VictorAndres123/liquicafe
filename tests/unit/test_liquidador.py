"""Reglas de recepción y cadena de ajustes del liquidador.

Los valores esperados se calculan a mano en cada prueba para que cualquiera
pueda revisarlos con una calculadora.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

import pytest

from app.business.domain.ajustes import ContextoLiquidacion, CuotaSostenimiento, a_pesos
from app.business.domain.errores import EntregaRechazada
from app.business.domain.models import DefectoTaza, LineaLiquidacion


def test_liquidacion_basica_fr94_una_carga(liquidador, precio_fnc, nueva_entrega):
    liq = liquidador.liquidar(nueva_entrega(), precio_fnc)
    # 125 kg x $17.760 = $2.220.000; cuota 1 % = $22.200
    assert liq.precio_kg == 17_760
    assert [linea.valor for linea in liq.lineas] == [2_220_000, -22_200]
    assert liq.neto == 2_197_800


def test_programa_especial_suma_bonificacion_antes_de_la_cuota(liquidador, precio_fnc, nueva_entrega, productor):
    asociado = replace(productor, programa_especial=True)
    liq = liquidador.liquidar(nueva_entrega(productor=asociado), precio_fnc)
    # 2.220.000 + 50.000 = 2.270.000; cuota 1 % = 22.700
    assert liq.neto == 2_247_300


def test_defecto_de_taza_descuenta_por_carga(liquidador, precio_fnc, nueva_entrega):
    entrega = nueva_entrega(
        kilos=Decimal("250"), factor_rendimiento=Decimal("91"), defecto=DefectoTaza.TIPO_I
    )
    liq = liquidador.liquidar(entrega, precio_fnc)
    # 250 kg x $18.115 = 4.528.750; tipo I: 2 cargas x 88.000 = 176.000
    # subtotal 4.352.750; cuota 43.527,5 -> 43.528 (redondeo al peso)
    assert [linea.valor for linea in liq.lineas] == [4_528_750, -176_000, -43_528]
    assert liq.neto == 4_309_222


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"humedad": Decimal("12.5")}, "Devolver para secado"),
        ({"humedad": Decimal("9.8")}, "sobresecado"),
        ({"factor_rendimiento": Decimal("100.5")}, "fuera de la tabla"),
        ({"factor_rendimiento": Decimal("87.9")}, "fuera de la tabla"),
        ({"kilos": Decimal("0")}, "mayor que cero"),
    ],
)
def test_entregas_fuera_de_rango_se_rechazan_con_mensaje_del_oficio(
    liquidador, precio_fnc, nueva_entrega, cambios, mensaje
):
    with pytest.raises(EntregaRechazada, match=mensaje):
        liquidador.liquidar(nueva_entrega(**cambios), precio_fnc)


def test_limites_de_humedad_son_inclusivos(liquidador, precio_fnc, nueva_entrega):
    for humedad in ("10.0", "12.0"):
        assert liquidador.liquidar(nueva_entrega(humedad=Decimal(humedad)), precio_fnc).neto > 0


def test_no_se_liquida_con_el_precio_de_otro_dia(liquidador, precio_fnc, nueva_entrega):
    with pytest.raises(ValueError):
        liquidador.liquidar(nueva_entrega(fecha=date(2026, 4, 10)), precio_fnc)


def test_la_liquidacion_guarda_copia_de_los_parametros(liquidador, precio_fnc, nueva_entrega):
    liq = liquidador.liquidar(nueva_entrega(), precio_fnc)
    assert liq.parametros["precio_carga_fr94"] == 2_220_000
    assert liq.parametros["precio_kg_aplicado"] == 17_760
    assert liq.parametros["bonificacion_programa_por_carga"] == 50_000
    assert "FNC" in liq.parametros["fuente_tabla"]


def test_agregar_una_regla_nueva_no_toca_otras_capas(liquidador, precio_fnc, nueva_entrega):
    """Escenario QA-02: la asamblea aprueba una bonificación por café de origen.

    Basta con una clase nueva y ubicarla antes de la cuota; ni la base de
    datos ni las vistas cambian, porque el desglose es una lista de líneas.
    """

    @dataclass(frozen=True)
    class BonificacionCafeDeOrigen:
        valor_por_carga: int = 30_000

        def aplicar(self, contexto: ContextoLiquidacion) -> LineaLiquidacion:
            return LineaLiquidacion(
                "Bonificación café de origen Pitalito",
                a_pesos(self.valor_por_carga * contexto.entrega.cargas),
            )

    *reglas, cuota = liquidador.ajustes
    assert isinstance(cuota, CuotaSostenimiento)
    nuevo = liquidador.con_ajustes([*reglas, BonificacionCafeDeOrigen(), cuota])

    liq = nuevo.liquidar(nueva_entrega(), precio_fnc)
    assert liq.lineas[1].concepto == "Bonificación café de origen Pitalito"
    # (2.220.000 + 30.000) - 1 % = 2.227.500
    assert liq.neto == 2_227_500
