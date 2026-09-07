"""Cronicas narradas por IA (fase 2).

Ningun endpoint de aqui llama a la API sin que se pida explicitamente:
/cronica/preparar solo mira los datos locales y avisa del coste.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Body

from .. import config, db as dbmod
from ..ai import chronicler, context as ctx
from ..errors import ProLegendsError
from .common import Conn, get_export

router = APIRouter(tags=["cronicas"])


def _ambito(payload: dict) -> dict:
    ambito = payload.get("ambito") or {}
    if not isinstance(ambito, dict) or "tipo" not in ambito:
        raise ProLegendsError("Falta indicar el ámbito de la crónica.")
    return ambito


@router.get("/cronicas/estado")
def estado():
    ok, motivo = chronicler.disponible()
    return {
        "disponible": ok,
        "motivo": motivo,
        "modelo": config.modelo_ia(),
    }


@router.post("/cronicas/preparar")
def preparar(payload: dict = Body(...), conn: sqlite3.Connection = Conn):
    """Muestra que se enviaria y si ya hay una versión guardada. NO llama a la API."""
    export_id = int(payload["export_id"])
    exp = get_export(conn, export_id)
    ambito = _ambito(payload)
    contexto = ctx.construir(conn, export_id, ambito)
    previa = chronicler.cacheada(conn, exp["world_id"], ambito)
    ok, motivo = chronicler.disponible()
    texto = ctx.a_texto(contexto) if contexto else ""
    return {
        "disponible": ok,
        "motivo": motivo,
        "modelo": config.modelo_ia(),
        "titulo": contexto.get("titulo"),
        "hechos": contexto.get("eventos_incluidos", 0),
        "caracteres_contexto": len(texto),
        "aproximado_tokens": len(texto) // 4,
        "ya_generada": bool(previa),
        "generada_el": previa["created_at"] if previa else None,
    }


@router.post("/cronicas")
def generar(payload: dict = Body(...), conn: sqlite3.Connection = Conn):
    export_id = int(payload["export_id"])
    exp = get_export(conn, export_id)
    ambito = _ambito(payload)
    resultado = chronicler.generar(
        conn, exp["world_id"], export_id, ambito, bool(payload.get("regenerar"))
    )
    return resultado


@router.get("/mundos/{world_id}/cronicas")
def listar(world_id: int, conn: sqlite3.Connection = Conn):
    filas = dbmod.all_(
        conn,
        """SELECT id, scope_type, scope_key, title, model, created_at
             FROM chronicles WHERE world_id = ? ORDER BY created_at DESC""",
        (world_id,),
    )
    return {"cronicas": filas}
