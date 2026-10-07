"""Errores esperados que la interfaz puede mostrar sin traceback."""


class POSException(Exception):
    """Error base del punto de venta."""


class ValidationError(POSException):
    """Una entrada no cumple las reglas del dominio."""


class NotFoundError(POSException):
    """No se encuentra el elemento solicitado."""


class StockError(POSException):
    """Una operacion de stock no puede completarse."""


class StateError(POSException):
    """El estado actual no permite la operacion."""


class PermissionDenied(POSException):
    """La sesion no tiene permiso para la operacion."""


class PersistenceError(POSException):
    """No se pueden cargar o guardar los datos."""
