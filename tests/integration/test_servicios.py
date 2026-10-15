"""Servicios de negocio contra una base SQLite real (archivo temporal)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal

import pytest

from app.business.domain.errores import (
    AutorizacionDeDatosRequerida,
    Conflicto,
    NoEncontrado,
    PrecioNoRegistrado,
    TransicionNoPermitida,
)
from app.business.domain.liquidador import Liquidador
from app.business.domain.models import DefectoTaza, EstadoLiquidacion
from app.business.services import (
    ServicioEntregas,
    ServicioPrecios,
    ServicioProductores,
    ServicioReportes,
)
from app.persistence import database
from app.persistence.repositories import RepositorioAuditoria
from tests.conftest import DIA_FNC

CEDULA = "1075123456"


@pytest.fixture
def ruta_bd(tmp_path):
    ruta = tmp_path / "liquicafe.db"
    database.inicializar(ruta)
    return ruta


@pytest.fixture
def uow(ruta_bd):
    return lambda: database.UnidadDeTrabajo(ruta_bd)


@pytest.fixture
def productores(uow):
    return ServicioProductores(uow, hoy=lambda: DIA_FNC)


@pytest.fixture
def precios(uow):
    return ServicioPrecios(uow, hoy=lambda: DIA_FNC)


@pytest.fixture
def entregas(uow, liquidador):
    return ServicioEntregas(uow, liquidador, hoy=lambda: DIA_FNC, ahora=lambda: datetime(2026, 4, 9, 8, 30))


@pytest.fixture
def con_precio_y_asociado(productores, precios):
    precios.registrar(fecha=DIA_FNC, precio_carga_fr94=2_220_000, precio_pasilla_kg=10_000)
    return productores.registrar(
        cedula=CEDULA, nombre="Luz Dary Muñoz", vereda="Bruselas", acepta_tratamiento_datos=True
    )


def _liquidar(entregas, **cambios):
    datos = dict(cedula=CEDULA, kilos=Decimal("125"), humedad=Decimal("11"), factor_rendimiento=Decimal("94"))
    datos.update(cambios)
    return entregas.registrar_y_liquidar(**datos)


def test_sin_autorizacion_de_datos_no_se_guarda_nada(productores):
    with pytest.raises(AutorizacionDeDatosRequerida):
        productores.registrar(cedula=CEDULA, nombre="Luz Dary", vereda="Bruselas", acepta_tratamiento_datos=False)
    assert productores.listar() == []


def test_no_se_repite_una_cedula(productores, con_precio_y_asociado):
    with pytest.raises(Conflicto):
        productores.registrar(cedula=CEDULA, nombre="Otra", vereda="Charguayaco", acepta_tratamiento_datos=True)


def test_no_se_liquida_sin_precio_del_dia(productores, entregas):
    productores.registrar(cedula=CEDULA, nombre="Luz Dary", vereda="Bruselas", acepta_tratamiento_datos=True)
    with pytest.raises(PrecioNoRegistrado):
        _liquidar(entregas)


def test_liquidacion_queda_guardada_tal_como_se_calculo(entregas, con_precio_y_asociado):
    creada = _liquidar(entregas, kilos=Decimal("190.3"), factor_rendimiento=Decimal("92.4"))
    leida = entregas.obtener(creada.id)

    assert leida.entrega.kilos == Decimal("190.3")  # sin errores de punto flotante
    assert leida.lineas == creada.lineas
    assert leida.neto == creada.neto
    assert leida.parametros == creada.parametros
    assert [e.evento for e in entregas.auditoria(creada.id)] == ["CREADA"]


def test_cambiar_parametros_no_altera_liquidaciones_viejas(uow, parametros, entregas, con_precio_y_asociado):
    """RN-10 / QA-03: lo liquidado se explica con los valores de su día."""
    vieja = _liquidar(entregas)
    nuevos = {**parametros, "cuota_sostenimiento_porcentaje": "3.0"}
    otro_servicio = ServicioEntregas(uow, Liquidador.desde_parametros(nuevos), hoy=lambda: DIA_FNC)

    assert otro_servicio.obtener(vieja.id).neto == 2_197_800
    assert _liquidar(otro_servicio).neto == 2_220_000 - 66_600


def test_anular_deja_rastro_y_no_se_puede_repetir(entregas, con_precio_y_asociado):
    liq = _liquidar(entregas)
    anulada = entregas.anular(liq.id, motivo="Peso mal digitado", responsable="Gerente")
    assert anulada.estado is EstadoLiquidacion.ANULADA

    with pytest.raises(TransicionNoPermitida):
        entregas.anular(liq.id, motivo="otra vez", responsable="Gerente")
    # El segundo intento hizo ROLLBACK: la auditoría no registra nada de más.
    assert [e.evento for e in entregas.auditoria(liq.id)] == ["CREADA", "ANULADA"]


def test_una_liquidacion_pagada_no_se_anula(entregas, con_precio_y_asociado):
    liq = _liquidar(entregas)
    entregas.marcar_pagada(liq.id, responsable="Tesorera")
    with pytest.raises(TransicionNoPermitida):
        entregas.anular(liq.id, motivo="error", responsable="Gerente")


def test_la_base_de_datos_impide_borrar_o_alterar_valores(ruta_bd, entregas, con_precio_y_asociado):
    liq = _liquidar(entregas)
    with sqlite3.connect(ruta_bd) as conexion:
        with pytest.raises(sqlite3.DatabaseError, match="no se borran"):
            conexion.execute("DELETE FROM liquidaciones WHERE id = ?", (liq.id,))
        with pytest.raises(sqlite3.DatabaseError, match="no se modifican"):
            conexion.execute("UPDATE liquidaciones SET neto = 1 WHERE id = ?", (liq.id,))


def test_si_falla_la_auditoria_no_queda_liquidacion_a_medias(monkeypatch, entregas, con_precio_y_asociado):
    """QA-05: la liquidación y su auditoría se guardan juntas o no se guardan."""

    def falla(self, fila):
        raise RuntimeError("corte de energía simulado")

    monkeypatch.setattr(RepositorioAuditoria, "registrar", falla)
    with pytest.raises(RuntimeError):
        _liquidar(entregas)
    monkeypatch.undo()
    assert entregas.historial(CEDULA) == []


def test_historial_y_reporte_del_dia(uow, entregas, con_precio_y_asociado):
    _liquidar(entregas, kilos=Decimal("500"), factor_rendimiento=Decimal("90"))
    segunda = _liquidar(entregas, kilos=Decimal("20"), factor_rendimiento=Decimal("99"), defecto=DefectoTaza.TIPO_III)
    entregas.anular(segunda.id, motivo="Duplicada", responsable="Gerente")

    assert len(entregas.historial(CEDULA)) == 2
    reporte = ServicioReportes(uow).diario(DIA_FNC)
    assert (reporte.entregas, reporte.anuladas, reporte.kilos) == (1, 1, Decimal("500"))


def test_historial_de_cedula_inexistente(entregas):
    with pytest.raises(NoEncontrado):
        entregas.historial("99999999")
