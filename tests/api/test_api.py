"""Pruebas de punta a punta: HTTP -> negocio -> SQLite y de vuelta."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from tests.conftest import DIA_FNC, RUTA_PARAMETROS

CEDULA = "1075123456"


@pytest.fixture
def cliente(tmp_path) -> TestClient:
    app = crear_app(
        ruta_bd=tmp_path / "api.db",
        ruta_parametros=RUTA_PARAMETROS,
        hoy=lambda: DIA_FNC,
        ahora=lambda: datetime(2026, 4, 9, 9, 0),
    )
    return TestClient(app)


@pytest.fixture
def preparado(cliente) -> TestClient:
    cliente.post("/api/precios", json={"fecha": "2026-04-09", "precio_carga_fr94": 2220000, "precio_pasilla_kg": 10000})
    cliente.post(
        "/api/productores",
        json={"cedula": CEDULA, "nombre": "Luz Dary Muñoz", "vereda": "Bruselas", "acepta_tratamiento_datos": True},
    )
    return cliente


def _entrega(**cambios):
    datos = {"cedula": CEDULA, "kilos": "125", "humedad": "11.0", "factor_rendimiento": "94"}
    datos.update(cambios)
    return datos


class TestApi:
    def test_liquidar_devuelve_desglose_y_cedula_enmascarada(self, preparado):
        respuesta = preparado.post("/api/liquidaciones", json=_entrega())
        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["neto"] == 2_197_800
        assert [l["valor"] for l in cuerpo["lineas"]] == [2_220_000, -22_200]
        assert cuerpo["productor"]["cedula"] == "******3456"
        assert CEDULA not in respuesta.text

    def test_regla_de_negocio_incumplida_responde_422_con_mensaje(self, preparado):
        respuesta = preparado.post("/api/liquidaciones", json=_entrega(humedad="13.0"))
        assert respuesta.status_code == 422
        assert "Devolver para secado" in respuesta.json()["detalle"]

    def test_formato_invalido_lo_rechaza_la_presentacion(self, preparado):
        respuesta = preparado.post("/api/liquidaciones", json=_entrega(kilos="-5"))
        assert respuesta.status_code == 422
        assert "detail" in respuesta.json()  # error de Pydantic, no llegó al negocio

    def test_sin_autorizacion_de_datos(self, cliente):
        respuesta = cliente.post(
            "/api/productores",
            json={"cedula": "12345678", "nombre": "Pedro", "vereda": "Criollo", "acepta_tratamiento_datos": False},
        )
        assert respuesta.status_code == 422
        assert "Ley 1581" in respuesta.json()["detalle"]

    def test_recursos_inexistentes_y_duplicados(self, preparado):
        assert preparado.get("/api/liquidaciones/999").status_code == 404
        duplicado = preparado.post("/api/precios", json={"fecha": "2026-04-09", "precio_carga_fr94": 1, "precio_pasilla_kg": 1})
        assert duplicado.status_code == 409

    def test_anular_pagar_historial_y_reporte(self, preparado):
        primera = preparado.post("/api/liquidaciones", json=_entrega()).json()
        segunda = preparado.post("/api/liquidaciones", json=_entrega(kilos="62.5")).json()

        anulada = preparado.post(
            f"/api/liquidaciones/{segunda['id']}/anulacion", json={"motivo": "Entrega duplicada", "responsable": "Gerente"}
        )
        assert anulada.json()["estado"] == "ANULADA"
        pagada = preparado.post(f"/api/liquidaciones/{primera['id']}/pago", json={"responsable": "Tesorera"})
        assert pagada.json()["estado"] == "PAGADA"

        historial = preparado.post("/api/historial", json={"cedula": CEDULA}).json()
        assert {l["estado"] for l in historial} == {"ANULADA", "PAGADA"}

        reporte = preparado.get("/api/reportes/diario", params={"fecha": "2026-04-09"}).json()
        assert reporte["entregas"] == 1 and reporte["anuladas"] == 1
        assert reporte["valor_neto"] == 2_197_800


class TestVistas:
    def test_recibo_avisa_si_falta_el_precio(self, cliente):
        pagina = cliente.get("/recibo")
        assert pagina.status_code == 200
        assert "Todavía no hay precio para hoy" in pagina.text

    def test_flujo_de_recibo_hasta_el_comprobante(self, preparado):
        respuesta = preparado.post(
            "/recibo",
            data={"cedula": CEDULA, "kilos": "190,3", "humedad": "11,2", "factor_rendimiento": "92,4", "defecto": "NINGUNO"},
        )
        assert respuesta.status_code == 200  # TestClient sigue la redirección 303
        assert "Comprobante de liquidación" in respuesta.text
        assert "190,3 kg" in respuesta.text  # coma decimal colombiana
        assert "******3456" in respuesta.text
        assert CEDULA not in respuesta.text

    def test_recibo_muestra_el_rechazo_en_el_formulario(self, preparado):
        respuesta = preparado.post(
            "/recibo", data={"cedula": CEDULA, "kilos": "100", "humedad": "9,1", "factor_rendimiento": "94"}
        )
        assert respuesta.status_code == 422
        assert "sobresecado" in respuesta.text
        assert 'value="100"' in respuesta.text  # no se pierde lo digitado

    def test_numero_mal_escrito_no_llega_al_negocio(self, preparado):
        respuesta = preparado.post(
            "/recibo", data={"cedula": CEDULA, "kilos": "ciento veinte", "humedad": "11", "factor_rendimiento": "94"}
        )
        assert respuesta.status_code == 422
        assert "Peso: escriba un número" in respuesta.text

    def test_historial_por_post_no_expone_la_cedula_en_la_url(self, preparado):
        preparado.post("/api/liquidaciones", json=_entrega())
        respuesta = preparado.post("/historial", data={"cedula": CEDULA})
        assert respuesta.status_code == 200
        assert CEDULA not in str(respuesta.url)
        assert "Luz Dary Muñoz" in respuesta.text

    def test_registro_de_asociado_y_precio_desde_formularios(self, cliente):
        sin_permiso = cliente.post("/productores", data={"cedula": "12345678", "nombre": "Pedro Rojas", "vereda": "Criollo"})
        assert sin_permiso.status_code == 422 and "Ley 1581" in sin_permiso.text

        ok = cliente.post(
            "/productores",
            data={"cedula": "12345678", "nombre": "Pedro Rojas", "vereda": "Criollo", "acepta_tratamiento_datos": "true"},
        )
        assert "Pedro Rojas" in ok.text and "****5678" in ok.text

        precio = cliente.post("/precio", data={"fecha": "2026-04-09", "precio_carga_fr94": "2220000", "precio_pasilla_kg": "10000"})
        assert "$ 2.220.000" in precio.text  # redirige al recibo con el precio vigente
        repetido = cliente.post("/precio", data={"fecha": "2026-04-09", "precio_carga_fr94": "1", "precio_pasilla_kg": "1"})
        assert repetido.status_code == 409

    def test_pagar_y_luego_intentar_anular_desde_el_comprobante(self, preparado):
        liq = preparado.post("/api/liquidaciones", json=_entrega()).json()
        pagina = preparado.post(f"/liquidaciones/{liq['id']}/pagar", data={"responsable": "Tesorera"})
        assert "PAGADA" in pagina.text and "Tesorera" in pagina.text

        intento = preparado.post(f"/liquidaciones/{liq['id']}/anular", data={"motivo": "error", "responsable": "Gerente"})
        assert intento.status_code == 422
        assert "ajuste contable" in intento.text

    def test_anular_desde_el_comprobante_y_ver_el_reporte(self, preparado):
        liq = preparado.post("/api/liquidaciones", json=_entrega()).json()
        anulada = preparado.post(f"/liquidaciones/{liq['id']}/anular", data={"motivo": "Peso mal digitado", "responsable": "Gerente"})
        assert "ANULADA" in anulada.text and "Peso mal digitado" in anulada.text

        reporte = preparado.get("/reporte", params={"fecha": "2026-04-09"})
        assert reporte.status_code == 200 and "Anuladas" in reporte.text
        assert preparado.get("/").url.path == "/recibo"

    def test_comprobante_inexistente_muestra_pagina_de_error(self, cliente):
        respuesta = cliente.get("/liquidaciones/12345")
        assert respuesta.status_code == 404
        assert "No existe la liquidación 12345" in respuesta.text
