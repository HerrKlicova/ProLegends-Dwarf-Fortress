"""Utilidades compartidas por los endpoints."""

from __future__ import annotations

import colorsys
import hashlib
import json
import sqlite3
from typing import Any, Optional

from fastapi import Depends

from .. import db as dbmod
from ..errors import NotFoundError


def get_conn():
    conn = dbmod.connect()
    try:
        dbmod.init_db(conn)
        yield conn
    finally:
        conn.close()


Conn = Depends(get_conn)


def color_for(clave: str) -> str:
    """Color estable deducido del propio dato (nombre de raza o de faccion).

    No hay ninguna paleta fija por mundo: el mismo texto da siempre el mismo
    color, y textos distintos dan colores bien separados.
    """
    if not clave:
        return "#8a8f98"
    digest = hashlib.md5(clave.encode("utf-8")).digest()
    tono = digest[0] / 255.0
    saturacion = 0.45 + (digest[1] / 255.0) * 0.35
    luz = 0.48 + (digest[2] / 255.0) * 0.18
    r, g, b = colorsys.hls_to_rgb(tono, luz, saturacion)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def load_json(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def get_export(conn: sqlite3.Connection, export_id: int) -> dict:
    row = dbmod.one(conn, "SELECT * FROM exports WHERE id = ?", (export_id,))
    if row is None:
        raise NotFoundError(f"No existe el export numero {export_id}.")
    if row["status"] != "ok":
        raise NotFoundError(
            f"El export '{row['prefix']}' no se importo correctamente.",
            row["message"] or "",
        )
    return row


def get_world(conn: sqlite3.Connection, world_id: int) -> dict:
    row = dbmod.one(conn, "SELECT * FROM worlds WHERE id = ?", (world_id,))
    if row is None:
        raise NotFoundError(f"No existe el mundo numero {world_id}.")
    return row


def world_exports(conn: sqlite3.Connection, world_id: int) -> list[dict]:
    """Exports correctos de un mundo, del mas antiguo al mas reciente."""
    return dbmod.all_(
        conn,
        """SELECT * FROM exports WHERE world_id = ? AND status = 'ok'
            ORDER BY COALESCE(game_year, 0), COALESCE(game_month, 0),
                     COALESCE(game_day, 0), id""",
        (world_id,),
    )


def latest_export(conn: sqlite3.Connection, world_id: int) -> dict:
    exports = world_exports(conn, world_id)
    if not exports:
        raise NotFoundError("Ese mundo no tiene ningun export importado correctamente.")
    return exports[-1]


def entity_index(conn: sqlite3.Connection, export_id: int) -> dict[int, dict]:
    """Todas las entidades del export indexadas por id, con su color."""
    salida: dict[int, dict] = {}
    for row in dbmod.all_(
        conn,
        """SELECT entity_id, name, type, race, parent_id, root_id, depth
             FROM entities WHERE export_id = ?""",
        (export_id,),
    ):
        row["color"] = color_for(row["race"] or row["name"] or str(row["entity_id"]))
        salida[row["entity_id"]] = row
    return salida


def hf_names(conn: sqlite3.Connection, export_id: int, ids: list[int]) -> dict[int, str]:
    ids = [i for i in dict.fromkeys(ids) if i is not None]
    if not ids:
        return {}
    salida: dict[int, str] = {}
    for trozo in _chunks(ids, 400):
        marcas = ",".join("?" * len(trozo))
        for row in conn.execute(
            f"SELECT hf_id, name FROM historical_figures WHERE export_id = ? AND hf_id IN ({marcas})",
            (export_id, *trozo),
        ):
            salida[row["hf_id"]] = row["name"]
    return salida


def site_names(conn: sqlite3.Connection, export_id: int, ids: list[int]) -> dict[int, str]:
    ids = [i for i in dict.fromkeys(ids) if i is not None]
    if not ids:
        return {}
    salida: dict[int, str] = {}
    for trozo in _chunks(ids, 400):
        marcas = ",".join("?" * len(trozo))
        for row in conn.execute(
            f"SELECT site_id, name FROM sites WHERE export_id = ? AND site_id IN ({marcas})",
            (export_id, *trozo),
        ):
            salida[row["site_id"]] = row["name"]
    return salida


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def event_payload(row: dict, incluir_json: bool = True) -> dict:
    """Convierte una fila de evento en algo presentable, sin inventar campos."""
    datos = load_json(row.get("data_json")) if incluir_json else {}
    for clave in ("id", "type", "year", "seconds72"):
        datos.pop(clave, None)
    return {
        "id": row.get("event_id"),
        "anyo": row.get("year"),
        "tipo": row.get("type"),
        "site_id": row.get("site_id"),
        "hfid": row.get("hfid"),
        "slayer_hfid": row.get("slayer_hfid"),
        "civ_id": row.get("civ_id"),
        "attacker_civ_id": row.get("attacker_civ_id"),
        "defender_civ_id": row.get("defender_civ_id"),
        "artifact_id": row.get("artifact_id"),
        "detalles": {k: v for k, v in datos.items() if v not in (None, "", [], {})},
    }
