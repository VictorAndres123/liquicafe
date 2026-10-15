"""Errores del dominio.

Todos heredan de ``ErrorDeNegocio``. La capa de presentación los traduce a
códigos HTTP según la familia (no encontrado, conflicto, validación), así que
aquí no aparece ningún detalle de HTTP. Los mensajes se muestran tal cual al
usuario, por eso están escritos en el lenguaje de la bodega.
"""


class ErrorDeNegocio(Exception):
    """Se violó una regla de negocio. El mensaje es apto para el usuario final."""


class DatoInvalido(ErrorDeNegocio):
    """Un dato tiene formato válido pero no tiene sentido para el negocio."""


class EntregaRechazada(ErrorDeNegocio):
    """La entrega no cumple las condiciones de recepción (RN-04, RN-05)."""


class AutorizacionDeDatosRequerida(ErrorDeNegocio):
    """Falta la autorización de tratamiento de datos (Ley 1581 de 2012, art. 9)."""


class PrecioNoRegistrado(ErrorDeNegocio):
    """No se puede liquidar sin el precio del día."""


class TransicionNoPermitida(ErrorDeNegocio):
    """El estado actual de la liquidación no admite la operación pedida."""


class NoEncontrado(ErrorDeNegocio):
    """El recurso pedido no existe."""


class Conflicto(ErrorDeNegocio):
    """El recurso ya existe y no se puede crear de nuevo."""
