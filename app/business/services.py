"""Servicios de aplicación: un método por caso de uso.

Cada método sigue el mismo guion: abre una unidad de trabajo (el límite de
la transacción), lee con los repositorios, le pide al dominio que aplique
las reglas y guarda el resultado con su rastro de auditoría. Aquí no hay
reglas de dinero (viven en ``domain``) ni nada de HTTP (vive en
``presentation``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Callable

from app.business import mapeo
from app.business.domain.errores import (
    AutorizacionDeDatosRequerida,
    Conflicto,
    DatoInvalido,
    NoEncontrado,
    PrecioNoRegistrado,
)
from app.business.domain.liquidador import Liquidador
from app.business.domain.models import (
    Cedula,
    DefectoTaza,
    Entrega,
    EventoAuditoria,
    Liquidacion,
    PrecioDelDia,
    Productor,
)
from app.business.domain.reportes import ReporteDiario
from app.persistence.database import UnidadDeTrabajo

FabricaUnidadDeTrabajo = Callable[[], UnidadDeTrabajo]
Reloj = Callable[[], date]
RelojConHora = Callable[[], datetime]


class ServicioProductores:
    def __init__(self, uow: FabricaUnidadDeTrabajo, hoy: Reloj = date.today) -> None:
        self._uow = uow
        self._hoy = hoy

    def registrar(
        self,
        *,
        cedula: str,
        nombre: str,
        vereda: str,
        acepta_tratamiento_datos: bool,
        telefono: str | None = None,
        programa_especial: bool = False,
    ) -> Productor:
        """RF-01 con la regla RN-12: sin autorización no se guarda ni un dato."""
        if not acepta_tratamiento_datos:
            raise AutorizacionDeDatosRequerida(
                "El asociado debe autorizar el tratamiento de sus datos personales "
                "(Ley 1581 de 2012, art. 9) antes de registrarlo."
            )
        if len(nombre.strip()) < 3 or not vereda.strip():
            raise DatoInvalido("Nombre y vereda son obligatorios.")
        productor = Productor(
            cedula=Cedula(cedula),
            nombre=nombre.strip(),
            vereda=vereda.strip(),
            telefono=(telefono or "").strip() or None,
            programa_especial=programa_especial,
            fecha_autorizacion_datos=self._hoy(),
        )
        with self._uow() as uow:
            if uow.productores.buscar_por_cedula(productor.cedula.numero):
                raise Conflicto(f"Ya existe un asociado con la cédula {productor.cedula}.")
            nuevo_id = uow.productores.insertar(mapeo.fila_productor(productor))
        return replace(productor, id=nuevo_id)

    def obtener(self, cedula: str) -> Productor:
        numero = Cedula(cedula).numero
        with self._uow() as uow:
            fila = uow.productores.buscar_por_cedula(numero)
        if fila is None:
            raise NoEncontrado(f"No hay un asociado con la cédula {Cedula(numero)}.")
        return mapeo.a_productor(fila)

    def listar(self) -> list[Productor]:
        with self._uow() as uow:
            return [mapeo.a_productor(fila) for fila in uow.productores.listar()]


class ServicioPrecios:
    def __init__(self, uow: FabricaUnidadDeTrabajo, hoy: Reloj = date.today) -> None:
        self._uow = uow
        self._hoy = hoy

    def registrar(self, *, fecha: date, precio_carga_fr94: int, precio_pasilla_kg: int) -> PrecioDelDia:
        """RF-02. Un precio por fecha y sin sobrescribir: ya pudo usarse para liquidar."""
        precio = PrecioDelDia(fecha, precio_carga_fr94, precio_pasilla_kg)
        with self._uow() as uow:
            if uow.precios.obtener(fecha.isoformat()):
                raise Conflicto(f"Ya hay un precio registrado para el {fecha.isoformat()}.")
            uow.precios.insertar(mapeo.fila_precio(precio))
        return precio

    def obtener(self, fecha: date) -> PrecioDelDia | None:
        with self._uow() as uow:
            fila = uow.precios.obtener(fecha.isoformat())
        return mapeo.a_precio(fila) if fila else None

    def de_hoy(self) -> PrecioDelDia | None:
        return self.obtener(self._hoy())

    def fecha_de_hoy(self) -> date:
        """La fecha la decide el reloj del negocio, no el de la vista (facilita las pruebas)."""
        return self._hoy()


class ServicioEntregas:
    def __init__(
        self,
        uow: FabricaUnidadDeTrabajo,
        liquidador: Liquidador,
        hoy: Reloj = date.today,
        ahora: RelojConHora = datetime.now,
    ) -> None:
        self._uow = uow
        self._liquidador = liquidador
        self._hoy = hoy
        self._ahora = ahora

    def registrar_y_liquidar(
        self,
        *,
        cedula: str,
        kilos: Decimal,
        humedad: Decimal,
        factor_rendimiento: Decimal,
        defecto: DefectoTaza = DefectoTaza.NINGUNO,
        responsable: str = "Recibo",
    ) -> Liquidacion:
        """RF-03 y RF-04 en una sola transacción: o queda todo guardado o nada."""
        fecha = self._hoy()
        with self._uow() as uow:
            fila_productor = uow.productores.buscar_por_cedula(Cedula(cedula).numero)
            if fila_productor is None:
                raise NoEncontrado(f"No hay un asociado con la cédula {Cedula(cedula)}.")
            fila_precio = uow.precios.obtener(fecha.isoformat())
            if fila_precio is None:
                raise PrecioNoRegistrado(
                    f"No hay precio registrado para hoy ({fecha.isoformat()}). "
                    "La gerencia debe registrarlo antes de recibir café."
                )
            entrega = Entrega(
                productor=mapeo.a_productor(fila_productor),
                fecha=fecha,
                kilos=kilos,
                humedad=humedad,
                factor_rendimiento=factor_rendimiento,
                defecto=defecto,
            )
            liquidacion = self._liquidador.liquidar(entrega, mapeo.a_precio(fila_precio))
            nuevo_id = uow.liquidaciones.insertar(mapeo.fila_liquidacion(liquidacion))
            self._auditar(uow, nuevo_id, "CREADA", f"Neto ${liquidacion.neto}", responsable)
        return replace(liquidacion, id=nuevo_id)

    def obtener(self, id_: int) -> Liquidacion:
        with self._uow() as uow:
            return self._cargar(uow, id_)

    def historial(self, cedula: str) -> list[Liquidacion]:
        with self._uow() as uow:
            fila_productor = uow.productores.buscar_por_cedula(Cedula(cedula).numero)
            if fila_productor is None:
                raise NoEncontrado(f"No hay un asociado con la cédula {Cedula(cedula)}.")
            filas = uow.liquidaciones.listar_por_productor(fila_productor["id"])
        return [mapeo.a_liquidacion(fila) for fila in filas]

    def anular(self, id_: int, *, motivo: str, responsable: str) -> Liquidacion:
        """RF-08. La regla de cuándo se puede anular la decide el dominio."""
        with self._uow() as uow:
            anulada = self._cargar(uow, id_).anular(motivo, responsable)
            uow.liquidaciones.actualizar_estado(
                id_, anulada.estado.value, anulada.motivo_anulacion, anulada.responsable_anulacion
            )
            self._auditar(uow, id_, "ANULADA", anulada.motivo_anulacion, anulada.responsable_anulacion)
        return anulada

    def marcar_pagada(self, id_: int, *, responsable: str) -> Liquidacion:
        """RF-10."""
        with self._uow() as uow:
            pagada = self._cargar(uow, id_).marcar_pagada()
            uow.liquidaciones.actualizar_estado(id_, pagada.estado.value)
            self._auditar(uow, id_, "PAGADA", None, responsable)
        return pagada

    def auditoria(self, id_: int) -> list[EventoAuditoria]:
        with self._uow() as uow:
            self._cargar(uow, id_)
            return [mapeo.a_evento(fila) for fila in uow.auditoria.listar(id_)]

    @staticmethod
    def _cargar(uow: UnidadDeTrabajo, id_: int) -> Liquidacion:
        fila = uow.liquidaciones.obtener(id_)
        if fila is None:
            raise NoEncontrado(f"No existe la liquidación {id_}.")
        return mapeo.a_liquidacion(fila)

    def _auditar(self, uow: UnidadDeTrabajo, id_: int, evento: str, detalle: str | None, responsable: str | None) -> None:
        uow.auditoria.registrar(
            {
                "liquidacion_id": id_,
                "evento": evento,
                "detalle": detalle,
                "responsable": responsable or "Sin dato",
                "momento": self._ahora().isoformat(timespec="seconds"),
            }
        )


class ServicioReportes:
    def __init__(self, uow: FabricaUnidadDeTrabajo) -> None:
        self._uow = uow

    def diario(self, fecha: date) -> ReporteDiario:
        """RF-09. Lee aquí y deja que el dominio haga las cuentas."""
        with self._uow() as uow:
            filas = uow.liquidaciones.listar_por_fecha(fecha.isoformat())
        return ReporteDiario.desde(fecha, [mapeo.a_liquidacion(fila) for fila in filas])


@dataclass(frozen=True)
class Servicios:
    """Fachada que la capa de presentación recibe ya armada desde ``app.main``."""

    productores: ServicioProductores
    precios: ServicioPrecios
    entregas: ServicioEntregas
    reportes: ServicioReportes
