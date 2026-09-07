"""Mundos, exports e importacion."""

from __future__ import annotations

import sqlite3
import threading
from typing import Optional

from fastapi import APIRouter, Body

from .. import config, db as dbmod
from ..errors import ProLegendsError
from . import common
from .common import Conn, get_export, get_world, load_json, world_exports

router = APIRouter(tags=["mundos"])

# Estado de la importacion en curso (la interfaz lo consulta para la barra).
_import_state: dict = {"activo": False, "lineas": [], "resultado": None, "error": None}
_import_lock = threading.Lock()


@router.get("/mundos")
def listar_mundos(conn: sqlite3.Connection = Conn):
    mundos = dbmod.all_(conn, "SELECT * FROM worlds ORDER BY name")
    salida = []
    for mundo in mundos:
        exports = [
            {
                "id": e["id"],
                "prefix": e["prefix"],
                "anyo": e["game_year"],
                "mes": e["game_month"],
                "dia": e["game_day"],
                "ancho": e["world_width"],
                "alto": e["world_height"],
                "anyo_min": e["min_year"],
                "anyo_max": e["max_year"],
                "aviso": e["message"],
                "importado": e["imported_at"],
                "resumen": load_json(e["counts_json"]),
            }
            for e in world_exports(conn, mundo["id"])
        ]
        if not exports:
            continue
        salida.append(
            {
                "id": mundo["id"],
                "nombre": mundo["name"],
                "altnombre": mundo["altname"],
                "exports": exports,
            }
        )
    fallidos = dbmod.all_(
        conn, "SELECT prefix, message FROM exports WHERE status <> 'ok'"
    )
    return {"mundos": salida, "fallidos": fallidos}


@router.get("/exports/{export_id}")
def detalle_export(export_id: int, conn: sqlite3.Connection = Conn):
    exp = get_export(conn, export_id)
    mundo = get_world(conn, exp["world_id"])
    meta = {
        r["key"]: r["value"]
        for r in dbmod.all_(conn, "SELECT key, value FROM world_meta WHERE export_id = ?", (export_id,))
    }
    return {
        "id": exp["id"],
        "prefix": exp["prefix"],
        "mundo": {"id": mundo["id"], "nombre": mundo["name"], "altnombre": mundo["altname"]},
        "fecha": {"anyo": exp["game_year"], "mes": exp["game_month"], "dia": exp["game_day"]},
        "mapa": {
            "ancho": exp["world_width"],
            "alto": exp["world_height"],
            "min_x": exp["min_x"],
            "min_y": exp["min_y"],
            "max_x": exp["max_x"],
            "max_y": exp["max_y"],
        },
        "anyos": {"min": exp["min_year"], "max": exp["max_year"]},
        "resumen": load_json(exp["counts_json"]),
        "aviso": exp["message"],
        "meta": meta,
    }


# ------------------------------------------------------------- importacion
def _run_import(prefijo: Optional[str]) -> None:
    from ..parser.importer import import_all

    lineas: list[str] = []

    def log(msg: str) -> None:
        texto = str(msg).strip()
        if texto:
            lineas.append(texto)
            del lineas[:-200]
        print(msg)

    conn = dbmod.connect()
    try:
        dbmod.init_db(conn)
        resultado = import_all(conn, verbose=True, log=log, only_prefix=prefijo)
        with _import_lock:
            _import_state["resultado"] = resultado
            _import_state["error"] = None
    except ProLegendsError as exc:
        with _import_lock:
            _import_state["error"] = exc.message
    except Exception as exc:  # pragma: no cover
        with _import_lock:
            _import_state["error"] = f"Fallo inesperado durante la importacion: {exc}"
    finally:
        conn.close()
        # Los identificadores de export pueden reutilizarse tras reimportar:
        # la paleta cacheada tiene que caducar con ellos.
        common._PALETAS.clear()
        with _import_lock:
            _import_state["activo"] = False
            _import_state["lineas"] = lineas


@router.post("/importar")
def importar(payload: dict = Body(default={})):
    with _import_lock:
        if _import_state["activo"]:
            return {"estado": "ya_en_marcha"}
        _import_state.update({"activo": True, "lineas": [], "resultado": None, "error": None})
    hilo = threading.Thread(
        target=_run_import, args=(payload.get("prefijo"),), daemon=True
    )
    hilo.start()
    return {"estado": "en_marcha", "carpeta": str(config.IMPORTS_DIR)}


@router.get("/importar/estado")
def estado_importacion():
    with _import_lock:
        return dict(_import_state)


@router.get("/importar/pendientes")
def pendientes(conn: sqlite3.Connection = Conn):
    """Que hay en data/imports/ y que falta por importar."""
    from ..parser.discover import discover

    pares, avisos = discover(config.IMPORTS_DIR)
    salida = []
    for par in pares:
        fila = dbmod.one(
            conn, "SELECT id, status FROM exports WHERE fingerprint = ?", (par.fingerprint(),)
        )
        salida.append(
            {
                "prefix": par.prefix,
                "completo": par.complete,
                "principal": par.main.name if par.main else None,
                "plus": par.plus.name if par.plus else None,
                "tamano_mb": round(
                    sum(p.stat().st_size for p in (par.main, par.plus) if p) / 1048576, 1
                ),
                "importado": bool(fila and fila["status"] == "ok"),
            }
        )
    return {"carpeta": str(config.IMPORTS_DIR), "exports": salida, "avisos": avisos}
