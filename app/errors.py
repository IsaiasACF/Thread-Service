"""Errores de persistencia independientes del driver y del transporte HTTP."""


class PersistenceError(Exception):
    """La operación de almacenamiento no pudo completarse."""


class PersistenceUnavailable(PersistenceError):
    """No se pudo contactar al almacenamiento o se perdió la conexión."""
