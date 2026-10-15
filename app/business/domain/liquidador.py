"""Servicio de dominio que convierte una entrega en una liquidación.

Es la pieza más valiosa del sistema y por eso no depende de nada externo:
recibe objetos y devuelve objetos. La capa de negocio decide cuándo llamarlo
y la de persistencia guarda lo que devuelve.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from app.business.domain.ajustes import (
    Ajuste,
    BonificacionProgramaEspecial,
    ContextoLiquidacion,
    CuotaSostenimiento,
    DescuentoPorTaza,
    ValorPorFactor,
)
from app.business.domain.errores import EntregaRechazada
from app.business.domain.models import DefectoTaza, Entrega, Liquidacion, PrecioDelDia
from app.business.domain.tabla_fr import TablaFactorRendimiento
from app.business.domain.texto import decimal_es


class Liquidador:
    """Aplica las reglas de recepción (RN-04, RN-05) y la cadena de ajustes."""

    def __init__(
        self,
        tabla: TablaFactorRendimiento,
        ajustes: Sequence[Ajuste],
        humedad_minima: Decimal,
        humedad_maxima: Decimal,
        parametros: Mapping[str, Any],
    ) -> None:
        self.tabla = tabla
        self.ajustes = tuple(ajustes)
        self.humedad_minima = humedad_minima
        self.humedad_maxima = humedad_maxima
        self._parametros = dict(parametros)

    @classmethod
    def desde_parametros(cls, parametros: Mapping[str, Any]) -> Liquidador:
        """Arma el liquidador a partir del diccionario de configuración.

        El orden de la lista importa: la cuota se calcula sobre el subtotal
        que dejan las demás reglas, así que siempre va de última.
        """
        tabla = TablaFactorRendimiento(
            {int(fr): Decimal(kg) for fr, kg in parametros["kg_pasilla_por_carga"].items()},
            fuente=parametros["fuente_tabla"],
        )
        descuentos = {
            DefectoTaza(nombre): int(valor)
            for nombre, valor in parametros["descuentos_taza_por_carga"].items()
        }
        ajustes: list[Ajuste] = [
            ValorPorFactor(),
            DescuentoPorTaza(descuentos),
            BonificacionProgramaEspecial(int(parametros["bonificacion_programa_por_carga"])),
            CuotaSostenimiento(Decimal(parametros["cuota_sostenimiento_porcentaje"])),
        ]
        return cls(
            tabla=tabla,
            ajustes=ajustes,
            humedad_minima=Decimal(parametros["humedad_minima"]),
            humedad_maxima=Decimal(parametros["humedad_maxima"]),
            parametros=parametros,
        )

    def con_ajustes(self, ajustes: Sequence[Ajuste]) -> Liquidador:
        """Copia del liquidador con otra lista de reglas (útil para pruebas y cambios)."""
        return Liquidador(self.tabla, ajustes, self.humedad_minima, self.humedad_maxima, self._parametros)

    def validar_recepcion(self, entrega: Entrega) -> None:
        """Rechaza la entrega con un mensaje que el recibidor le pueda leer al asociado."""
        if entrega.kilos <= 0:
            raise EntregaRechazada("El peso debe ser mayor que cero.")
        if entrega.humedad > self.humedad_maxima:
            raise EntregaRechazada(
                f"Humedad de {decimal_es(entrega.humedad)} %: el café está húmedo. "
                f"Devolver para secado (máximo {decimal_es(self.humedad_maxima)} %)."
            )
        if entrega.humedad < self.humedad_minima:
            raise EntregaRechazada(
                f"Humedad de {decimal_es(entrega.humedad)} %: el café está sobresecado "
                f"(mínimo {decimal_es(self.humedad_minima)} %). Se recibe solo por negociación aparte."
            )
        if not self.tabla.admite(entrega.factor_rendimiento):
            raise EntregaRechazada(
                f"FR {decimal_es(entrega.factor_rendimiento)} fuera de la tabla de la FNC "
                f"({decimal_es(self.tabla.fr_minimo)} a {decimal_es(self.tabla.fr_maximo)}). "
                "Requiere negociación aparte."
            )

    def liquidar(self, entrega: Entrega, precio: PrecioDelDia) -> Liquidacion:
        if precio.fecha != entrega.fecha:
            raise ValueError("La entrega se liquida con el precio de su mismo día.")
        self.validar_recepcion(entrega)
        precio_kg = self.tabla.precio_kg(entrega.factor_rendimiento, precio)

        lineas = []
        subtotal = 0
        for ajuste in self.ajustes:
            linea = ajuste.aplicar(ContextoLiquidacion(entrega, precio_kg, subtotal))
            if linea is not None:
                lineas.append(linea)
                subtotal += linea.valor

        return Liquidacion(
            entrega=entrega,
            precio_kg=precio_kg,
            lineas=tuple(lineas),
            parametros=self._copia_de_parametros(precio, precio_kg),
        )

    def _copia_de_parametros(self, precio: PrecioDelDia, precio_kg: int) -> dict[str, Any]:
        """Lo necesario para reconstruir el cálculo meses después (RN-10)."""
        return {
            "version_parametros": self._parametros.get("version"),
            "fuente_tabla": self.tabla.fuente,
            "precio_carga_fr94": precio.precio_carga_fr94,
            "precio_pasilla_kg": precio.precio_pasilla_kg,
            "precio_kg_aplicado": precio_kg,
            "humedad_aceptada": [str(self.humedad_minima), str(self.humedad_maxima)],
            "bonificacion_programa_por_carga": self._parametros.get("bonificacion_programa_por_carga"),
            "cuota_sostenimiento_porcentaje": self._parametros.get("cuota_sostenimiento_porcentaje"),
            "descuentos_taza_por_carga": self._parametros.get("descuentos_taza_por_carga"),
        }
