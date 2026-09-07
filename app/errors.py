"""Errores propios del dominio.

La regla es: cualquier fallo previsible (XML corrupto, fichero incompleto,
mundo inexistente) se convierte en uno de estos y llega a la interfaz como un
mensaje legible en castellano, nunca como un stack trace.
"""

from __future__ import annotations


class ProLegendsError(Exception):
    """Error controlado con mensaje apto para mostrar al usuario."""

    status_code = 400

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        return {"error": self.message, "detalle": self.detail}


class ImportError_(ProLegendsError):
    """Fallo durante la importacion de un export."""


class CorruptXMLError(ProLegendsError):
    """El XML no se ha podido parsear ni despues de sanearlo."""

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(
            f"El archivo '{path}' parece corrupto o incompleto y no se ha podido leer.",
            detail,
        )


class NotFoundError(ProLegendsError):
    status_code = 404
