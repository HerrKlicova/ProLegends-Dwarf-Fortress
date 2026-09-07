"""Ajustes que la aplicación recuerda entre arranques.

Son cosas que eliges una vez y no quieres volver a decir: dónde está instalado
Dwarf Fortress, cuál es tu fortaleza... Van en un JSON aparte, no en el `.env`
(que es tuyo, lo editas a mano y solo lleva la clave de la API) ni en la base de
datos (que se borra y se regenera con soltura).
"""

from __future__ import annotations

import json
import threading
from typing import Any

from pathlib import Path

from . import config

_CERROJO = threading.Lock()


def ruta() -> Path:
    return config.DATA_DIR / "ajustes.json"


def leer() -> dict:
    fichero = ruta()
    if not fichero.exists():
        return {}
    try:
        datos = json.loads(fichero.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar(cambios: dict) -> dict:
    """Mezcla los cambios con lo que ya hubiera y lo escribe."""
    with _CERROJO:
        actuales = leer()
        actuales.update(cambios)
        config.ensure_dirs()
        temporal = ruta().with_suffix(".json.tmp")
        temporal.write_text(
            json.dumps(actuales, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporal.replace(ruta())
        return actuales


def obtener(clave: str, por_defecto: Any = None) -> Any:
    return leer().get(clave, por_defecto)


def poner(clave: str, valor: Any) -> None:
    guardar({clave: valor})


def olvidar(clave: str) -> None:
    with _CERROJO:
        actuales = leer()
        if clave in actuales:
            actuales.pop(clave)
            config.ensure_dirs()
            ruta().write_text(
                json.dumps(actuales, ensure_ascii=False, indent=2), encoding="utf-8"
            )
