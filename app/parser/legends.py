"""Extraccion de registros del XML de legends a filas de la base de datos.

Aqui vive todo el conocimiento sobre COMO es el XML de Dwarf Fortress. El resto
de la aplicacion no deberia necesitar saber nada de etiquetas ni de estructura:
consulta la base de datos y punto.
"""

from __future__ import annotations

import json
from typing import Any, Optional

# ---------------------------------------------------------------- utilidades


def as_int(value: Any) -> Optional[int]:
    if value is None or value is True:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if value is True:
        return ""
    if isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def as_list(value: Any) -> list:
    """Normaliza a lista: el XML repite etiquetas para las colecciones."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_flag(value: Any) -> int:
    """Las banderas del XML son etiquetas vacias: <deity/>, <force/>..."""
    if value is None:
        return 0
    if value is True:
        return 1
    text = str(value).strip().lower()
    if text in ("", "true", "1", "yes"):
        return 1
    if text in ("false", "0", "no"):
        return 0
    return 1


def parse_coords(value: Any) -> tuple[Optional[int], Optional[int]]:
    """'32,25' -> (32, 25). Devuelve (None, None) si no se puede leer."""
    text = as_text(value)
    if not text:
        return None, None
    first = text.split()[0].split(":")[0]
    parts = first.split(",")
    if len(parts) < 2:
        return None, None
    return as_int(parts[0]), as_int(parts[1])


def jdump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def deep_merge(base: dict, extra: dict) -> dict:
    """Fusiona el registro del _plus sobre el del principal.

    Regla: el valor nuevo gana salvo que este vacio; los diccionarios se funden
    recursivamente y las listas se sustituyen (el _plus suele traerlas completas).
    """
    out = dict(base)
    for key, value in extra.items():
        if value in (None, ""):
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


# --------------------------------------------------------- eventos: columnas
# Campos que se sacan del JSON a columnas propias porque se consultan mucho.
EVENT_COLUMNS = (
    "site_id",
    "civ_id",
    "site_civ_id",
    "attacker_civ_id",
    "defender_civ_id",
    "hfid",
    "slayer_hfid",
    "entity_id",
    "artifact_id",
    "structure_id",
    "subregion_id",
)

# Sinonimos: distintas versiones de DF nombran lo mismo de formas distintas.
EVENT_ALIASES = {
    "hfid": ("hfid", "hf_id", "target_hfid", "histfig_id"),
    "slayer_hfid": ("slayer_hfid",),
    "site_id": ("site_id", "site"),
    "civ_id": ("civ_id",),
    "site_civ_id": ("site_civ_id",),
    "attacker_civ_id": ("attacker_civ_id",),
    "defender_civ_id": ("defender_civ_id",),
    "entity_id": ("entity_id", "entity", "entity_id_1"),
    "artifact_id": ("artifact_id", "artifact"),
    "structure_id": ("structure_id",),
    "subregion_id": ("subregion_id",),
}


def event_column(record: dict, column: str) -> Optional[int]:
    for key in EVENT_ALIASES.get(column, (column,)):
        if key in record:
            value = as_int(record[key])
            if value is not None:
                return value
    return None


# ------------------------------------------------ propiedad de los sitios
# Eventos que cambian quien manda en un sitio (trampa 6 del formato).
OWNERSHIP_CREATE = {"created site"}
OWNERSHIP_TAKEOVER = {"site taken over"}
OWNERSHIP_DESTROY = {"destroyed site", "hf destroyed site"}
OWNERSHIP_TYPES = OWNERSHIP_CREATE | OWNERSHIP_TAKEOVER | OWNERSHIP_DESTROY

STATE_ACTIVE = "activo"
STATE_RUINS = "ruinas"
STATE_UNKNOWN = "desconocido"


def ownership_change(record: dict, event_type: str) -> Optional[tuple[Optional[int], str]]:
    """Devuelve (nuevo_propietario, estado) o None si el evento no cambia nada."""
    if event_type in OWNERSHIP_CREATE:
        owner = event_column(record, "civ_id")
        if owner is None:
            owner = event_column(record, "site_civ_id")
        return owner, STATE_ACTIVE
    if event_type in OWNERSHIP_TAKEOVER:
        owner = event_column(record, "attacker_civ_id")
        if owner is None:
            owner = event_column(record, "new_site_civ_id")
        return owner, STATE_ACTIVE
    if event_type in OWNERSHIP_DESTROY:
        return None, STATE_RUINS
    return None


# --------------------------------------------- clasificacion de los sitios
# Capas del mapa. Se deducen del tipo de sitio que trae el XML, sin listas
# cerradas de mundos ni de civilizaciones concretas.
def site_layer(site_type: Optional[str]) -> str:
    t = (site_type or "").lower()
    if "vault" in t:
        return "boveda"
    if "tower" in t or "necro" in t:
        return "torre"
    if "lair" in t or "labyrinth" in t or "shrine" in t or "camp" in t:
        return "guarida"
    if "cave" in t or "burrow" in t:
        return "cueva"
    if "tomb" in t or "mausoleum" in t:
        return "tumba"
    return "asentamiento"


# Tipos de figura que cuentan como "bestia" para los avisos de cercania.
BEAST_TYPES = {
    "megabeast",
    "semimegabeast",
    "titan",
    "demon",
    "night creature",
    "forgotten beast",
}
