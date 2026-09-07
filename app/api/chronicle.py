"""Cronicas narradas por IA (fase 2).

Ningun endpoint de aqui llama a la API sin que se pida explicitamente:
/cronica/preparar solo mira los datos locales y avisa del coste.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Body

from .. import config
from ..ai import almacen, chronicler, context as ctx
from ..errors import NotFoundError, ProLegendsError
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
    """Las crónicas guardadas de un mundo, ya agrupadas por ámbito."""
    mundo = chronicler.nombre_mundo(conn, world_id)
    guardadas = almacen.listar(mundo)

    grupos = []
    for ambito in almacen.ORDEN_AMBITO:
        de_este = [c for c in guardadas if c.get("ambito") == ambito]
        if not de_este:
            continue
        grupos.append(
            {
                "ambito": ambito,
                "nombre": almacen.NOMBRES_AMBITO.get(ambito, ambito),
                "cronicas": sorted(de_este, key=_orden_dentro_del_grupo),
            }
        )
    # Cualquier ámbito que se añada en el futuro y no esté en la lista de arriba.
    conocidos = set(almacen.ORDEN_AMBITO)
    otros = [c for c in guardadas if c.get("ambito") not in conocidos]
    if otros:
        grupos.append({"ambito": "otros", "nombre": "Otras", "cronicas": otros})

    return {
        "mundo": mundo,
        "carpeta": str(almacen.carpeta_mundo(mundo)),
        "total": len(guardadas),
        "grupos": grupos,
    }


def _orden_dentro_del_grupo(cronica: dict):
    """Los años por su primer año; lo demás, por título."""
    clave = cronica.get("clave", "")
    if clave.startswith("anyos:"):
        try:
            return (0, int(clave.split(":", 1)[1].split("-")[0]), "")
        except (ValueError, IndexError):
            return (0, 0, clave)
    return (0, 0, (cronica.get("titulo") or clave).lower())


@router.get("/mundos/{world_id}/cronicas/{ambito}/{clave}")
def obtener(world_id: int, ambito: str, clave: str, conn: sqlite3.Connection = Conn):
    """El texto completo de una crónica ya guardada. No llama a la API."""
    mundo = chronicler.nombre_mundo(conn, world_id)
    datos = almacen.leer(mundo, ambito, clave)
    if datos is None:
        raise NotFoundError("Esa crónica ya no está guardada.")
    return datos
