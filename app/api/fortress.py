"""Panel de MI fortaleza: detección, resumen, novedades y avisos."""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Body, Query

from .. import config, db as dbmod
from ..errors import NotFoundError, ProLegendsError
from ..model import fortress as F
from .common import Conn, get_world, world_exports

router = APIRouter(tags=["fortaleza"])


@router.get("/mundos/{world_id}/fortaleza")
def fortaleza(
    world_id: int,
    radio: int = Query(None),
    conn: sqlite3.Connection = Conn,
):
    get_world(conn, world_id)
    radio = radio or config.DEFAULT_ALERT_RADIUS
    eleccion = F.resolve(conn, world_id)
    exports = world_exports(conn, world_id)
    if not exports:
        raise NotFoundError("Ese mundo no tiene ningún export importado correctamente.")

    salida = {
        "mundo_id": world_id,
        "export_id": eleccion["export_id"],
        "export_anterior": eleccion["export_anterior"],
        "exports": [
            {"id": e["id"], "prefix": e["prefix"], "anyo": e["game_year"]} for e in exports
        ],
        "seleccion": {
            "site_id": eleccion["site_id"],
            "origen": eleccion["origen"],
            "ambiguo": eleccion["ambiguo"],
            "candidatos": eleccion["candidatos"],
        },
        "resumen": None,
        "avisos": None,
        "novedades": None,
    }
    if eleccion["site_id"] is None:
        return salida

    salida["resumen"] = F.summary(conn, eleccion["export_id"], eleccion["site_id"])
    salida["avisos"] = F.alerts(conn, eleccion["export_id"], eleccion["site_id"], radio)
    if eleccion["export_anterior"]:
        salida["novedades"] = F.diff(
            conn,
            eleccion["export_anterior"],
            eleccion["export_id"],
            eleccion["site_id"],
            radio,
        )
    return salida


@router.post("/mundos/{world_id}/fortaleza")
def elegir(world_id: int, payload: dict = Body(...), conn: sqlite3.Connection = Conn):
    get_world(conn, world_id)
    site_id = payload.get("site_id")
    if site_id is None:
        F.forget(conn, world_id)
        return {"estado": "olvidada"}
    try:
        site_id = int(site_id)
    except (TypeError, ValueError):
        raise ProLegendsError("El identificador de sitio no es un número.")
    F.choose(conn, world_id, site_id)
    return {"estado": "guardada", "site_id": site_id}


@router.get("/mundos/{world_id}/diff")
def comparar(
    world_id: int,
    desde: Optional[int] = None,
    hasta: Optional[int] = None,
    radio: int = Query(None),
    conn: sqlite3.Connection = Conn,
):
    """Diferencias entre dos exports del mismo mundo."""
    get_world(conn, world_id)
    radio = radio or config.DEFAULT_ALERT_RADIUS
    exports = world_exports(conn, world_id)
    if len(exports) < 2:
        return {
            "posible": False,
            "motivo": "Hace falta al menos un segundo export del mismo mundo para comparar.",
            "exports": [{"id": e["id"], "prefix": e["prefix"], "anyo": e["game_year"]} for e in exports],
        }
    ids = [e["id"] for e in exports]
    if hasta is None:
        hasta = ids[-1]
    if hasta not in ids:
        raise NotFoundError("El export indicado no pertenece a este mundo.")
    if desde is None:
        posicion = ids.index(hasta)
        # El anterior al elegido; si el elegido es el primero, se compara con el
        # siguiente, que es lo único que tiene sentido.
        desde = ids[posicion - 1] if posicion > 0 else ids[1]
    if desde not in ids:
        raise NotFoundError("El export de partida no pertenece a este mundo.")
    if desde == hasta:
        raise ProLegendsError("Hay que comparar dos exports distintos.")

    eleccion = F.resolve(conn, world_id)
    resultado = F.diff(conn, desde, hasta, eleccion["site_id"], radio)
    nombres = {e["id"]: e["prefix"] for e in exports}
    return {
        "posible": True,
        "desde": {"id": desde, "prefix": nombres[desde]},
        "hasta": {"id": hasta, "prefix": nombres[hasta]},
        "site_id": eleccion["site_id"],
        "exports": [{"id": e["id"], "prefix": e["prefix"], "anyo": e["game_year"]} for e in exports],
        **resultado,
    }
