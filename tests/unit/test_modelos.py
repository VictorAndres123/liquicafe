"""Objetos de valor, transiciones de estado y reporte diario."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.business.domain.errores import DatoInvalido, TransicionNoPermitida
from app.business.domain.models import Cedula, EstadoLiquidacion
from app.business.domain.reportes import ReporteDiario
from tests.conftest import DIA_FNC


def test_la_cedula_se_enmascara_por_defecto():
    cedula = Cedula("1.075.123.456")
    assert cedula.numero == "1075123456"
    assert str(cedula) == "******3456"
    assert f"{cedula}" == "******3456"


@pytest.mark.parametrize("invalida", ["12A45", "123", "12345678901", ""])
def test_cedulas_invalidas_se_rechazan(invalida):
    with pytest.raises(DatoInvalido):
        Cedula(invalida)


def test_anular_conserva_la_liquidacion_con_motivo(liquidador, precio_fnc, nueva_entrega):
    liq = liquidador.liquidar(nueva_entrega(), precio_fnc)
    anulada = liq.anular("Se digitó mal el peso", "Gerente")
    assert anulada.estado is EstadoLiquidacion.ANULADA
    assert anulada.motivo_anulacion == "Se digitó mal el peso"
    assert anulada.neto == liq.neto  # el valor histórico no se pierde
    assert liq.estado is EstadoLiquidacion.VIGENTE  # el original no mutó


def test_no_se_anula_una_liquidacion_pagada(liquidador, precio_fnc, nueva_entrega):
    pagada = liquidador.liquidar(nueva_entrega(), precio_fnc).marcar_pagada()
    with pytest.raises(TransicionNoPermitida, match="ajuste contable"):
        pagada.anular("error", "Gerente")


def test_no_se_paga_una_liquidacion_anulada(liquidador, precio_fnc, nueva_entrega):
    anulada = liquidador.liquidar(nueva_entrega(), precio_fnc).anular("error", "Gerente")
    with pytest.raises(TransicionNoPermitida):
        anulada.marcar_pagada()


def test_anular_exige_motivo_y_responsable(liquidador, precio_fnc, nueva_entrega):
    liq = liquidador.liquidar(nueva_entrega(), precio_fnc)
    with pytest.raises(DatoInvalido):
        liq.anular("   ", "Gerente")


def test_reporte_pondera_el_fr_por_kilos_y_excluye_anuladas(liquidador, precio_fnc, nueva_entrega):
    grande = liquidador.liquidar(
        nueva_entrega(kilos=Decimal("500"), factor_rendimiento=Decimal("90")), precio_fnc
    )
    pequena = liquidador.liquidar(
        nueva_entrega(kilos=Decimal("20"), factor_rendimiento=Decimal("99")), precio_fnc
    )
    anulada = replace(grande, id=3).anular("duplicada", "Gerente")

    reporte = ReporteDiario.desde(DIA_FNC, [grande, pequena, anulada])

    assert reporte.entregas == 2
    assert reporte.anuladas == 1
    assert reporte.kilos == Decimal("520")
    # (500 x 90 + 20 x 99) / 520 = 90,35; un promedio simple daría 94,5
    assert reporte.fr_promedio_ponderado == Decimal("90.35")
    assert reporte.valor_neto == grande.neto + pequena.neto


def test_numeros_con_formato_colombiano():
    from app.business.domain.texto import decimal_es, pesos_es

    assert decimal_es(Decimal("13.4")) == "13,4"
    assert decimal_es(Decimal("1.0")) == "1"
    assert decimal_es(Decimal("1234.5"), 1) == "1.234,5"
    assert pesos_es(3_455_766) == "$ 3.455.766"
    assert pesos_es(-22_200) == "-$ 22.200"


def test_mensaje_de_rechazo_usa_coma_decimal(liquidador, precio_fnc, nueva_entrega):
    from app.business.domain.errores import EntregaRechazada

    with pytest.raises(EntregaRechazada, match=r"Humedad de 13,4 %.*máximo 12 %"):
        liquidador.liquidar(nueva_entrega(humedad=Decimal("13.4")), precio_fnc)
