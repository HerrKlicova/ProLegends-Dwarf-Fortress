"""Explorador de figuras historicas."""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Query

from .. import db as dbmod
from ..errors import NotFoundError
from .common import (
    Conn,
    color_for,
    entity_index,
    event_payload,
    get_export,
    hf_names,
    load_json,
    site_names,
)

router = APIRouter(tags=["figuras"])


@router.get("/exports/{export_id}/figuras")
def buscar(
    export_id: int,
    q: Optional[str] = None,
    raza: Optional[str] = None,
    vivas: Optional[bool] = None,
    tipo: Optional[str] = None,
    orden: str = "nombre",
    limite: int = Query(100, le=1000),
    conn: sqlite3.Connection = Conn,
):
    get_export(conn, export_id)
    sql = [
        """SELECT hf_id, name, race, caste, birth_year, death_year, alive,
                  associated_type, kills
             FROM historical_figures WHERE export_id = ?"""
    ]
    params: list = [export_id]
    if q:
        sql.append("AND name LIKE ?")
        params.append(f"%{q}%")
    if raza:
        sql.append("AND race = ?")
        params.append(raza)
    if tipo:
        sql.append("AND associated_type = ?")
        params.append(tipo)
    if vivas is not None:
        sql.append("AND alive = ?")
        params.append(1 if vivas else 0)
    sql.append({"muertes": "ORDER BY kills DESC, name", "nombre": "ORDER BY name"}.get(orden, "ORDER BY name"))
    sql.append("LIMIT ?")
    params.append(limite)
    filas = dbmod.all_(conn, " ".join(sql), tuple(params))
    total = conn.execute(
        "SELECT COUNT(*) FROM historical_figures WHERE export_id = ?", (export_id,)
    ).fetchone()[0]
    razas = dbmod.all_(
        conn,
        """SELECT race, COUNT(*) n FROM historical_figures
            WHERE export_id = ? AND race IS NOT NULL GROUP BY race ORDER BY n DESC""",
        (export_id,),
    )
    for fila in filas:
        fila["color"] = color_for(fila["race"] or "")
    return {"figuras": filas, "total": total, "razas": razas}


@router.get("/exports/{export_id}/matadores")
def matadores(export_id: int, limite: int = Query(50, le=500), conn: sqlite3.Connection = Conn):
    """Quien mato a quien: ranking por muertes causadas."""
    get_export(conn, export_id)
    filas = dbmod.all_(
        conn,
        """SELECT h.hf_id, h.name, h.race, h.associated_type, h.alive, h.kills
             FROM historical_figures h
            WHERE h.export_id = ? AND h.kills > 0
            ORDER BY h.kills DESC, h.name LIMIT ?""",
        (export_id, limite),
    )
    for fila in filas:
        fila["color"] = color_for(fila["race"] or "")
        victimas = dbmod.all_(
            conn,
            """SELECT e.hfid, e.year, v.name, v.race
                 FROM events e LEFT JOIN historical_figures v
                   ON v.export_id = e.export_id AND v.hf_id = e.hfid
                WHERE e.export_id = ? AND e.slayer_hfid = ?
                ORDER BY e.year LIMIT 12""",
            (export_id, fila["hf_id"]),
        )
        fila["victimas"] = victimas
    return {"matadores": filas}


@router.get("/exports/{export_id}/figuras/{hf_id}")
def ficha(export_id: int, hf_id: int, limite_eventos: int = 300, conn: sqlite3.Connection = Conn):
    get_export(conn, export_id)
    fig = dbmod.one(
        conn,
        "SELECT * FROM historical_figures WHERE export_id = ? AND hf_id = ?",
        (export_id, hf_id),
    )
    if fig is None:
        raise NotFoundError(f"No hay ninguna figura historica con el numero {hf_id}.")

    entidades = entity_index(conn, export_id)

    pertenencias = []
    for row in conn.execute(
        """SELECT entity_id, link_type, link_strength, former FROM hf_entity_links
            WHERE export_id = ? AND hf_id = ?""",
        (export_id, hf_id),
    ):
        ent = entidades.get(row["entity_id"])
        pertenencias.append(
            {
                "entidad_id": row["entity_id"],
                "entidad": ent["name"] if ent else None,
                "tipo_entidad": ent["type"] if ent else None,
                "raza": ent["race"] if ent else None,
                "vinculo": row["link_type"],
                "fuerza": row["link_strength"],
                "antiguo": bool(row["former"]),
            }
        )

    relaciones = []
    otros = []
    for row in conn.execute(
        "SELECT other_hf_id, link_type, link_strength FROM hf_links WHERE export_id = ? AND hf_id = ?",
        (export_id, hf_id),
    ):
        relaciones.append(
            {"hf_id": row["other_hf_id"], "vinculo": row["link_type"], "fuerza": row["link_strength"]}
        )
        otros.append(row["other_hf_id"])
    nombres = hf_names(conn, export_id, otros)
    for rel in relaciones:
        rel["nombre"] = nombres.get(rel["hf_id"])

    habilidades = dbmod.all_(
        conn,
        """SELECT skill, total_ip FROM hf_skills WHERE export_id = ? AND hf_id = ?
            ORDER BY total_ip DESC""",
        (export_id, hf_id),
    )
    rasgos: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT kind, value FROM hf_traits WHERE export_id = ? AND hf_id = ?", (export_id, hf_id)
    ):
        rasgos.setdefault(row["kind"], []).append(row["value"])

    vinculos_sitio = dbmod.all_(
        conn,
        "SELECT site_id, link_type FROM hf_site_links WHERE export_id = ? AND hf_id = ?",
        (export_id, hf_id),
    )
    nombres_sitio = site_names(conn, export_id, [v["site_id"] for v in vinculos_sitio])
    for v in vinculos_sitio:
        v["nombre"] = nombres_sitio.get(v["site_id"])

    artefactos = dbmod.all_(
        conn,
        """SELECT artifact_id, name, item, site_id FROM artifacts
            WHERE export_id = ? AND holder_hfid = ?""",
        (export_id, hf_id),
    )
    tramas = dbmod.all_(
        conn,
        "SELECT plot_idx, type, agreement_id, parent_plot_hfid, data_json FROM hf_plots WHERE export_id = ? AND hf_id = ?",
        (export_id, hf_id),
    )
    for trama in tramas:
        trama["detalles"] = load_json(trama.pop("data_json"))

    cargos = dbmod.all_(
        conn,
        """SELECT a.entity_id, p.name AS cargo, e.name AS entidad
             FROM entity_position_assignments a
             LEFT JOIN entity_positions p
                    ON p.export_id = a.export_id AND p.entity_id = a.entity_id
                   AND p.position_id = a.position_id
             LEFT JOIN entities e ON e.export_id = a.export_id AND e.entity_id = a.entity_id
            WHERE a.export_id = ? AND a.hfid = ?""",
        (export_id, hf_id),
    )

    eventos_raw = dbmod.all_(
        conn,
        """SELECT * FROM events
            WHERE export_id = ? AND (hfid = ? OR slayer_hfid = ?)
            ORDER BY year, seconds72 LIMIT ?""",
        (export_id, hf_id, hf_id, limite_eventos),
    )
    eventos = [event_payload(e) for e in eventos_raw]
    nombres_ev = hf_names(
        conn, export_id, [e["hfid"] for e in eventos] + [e["slayer_hfid"] for e in eventos]
    )
    sitios_ev = site_names(conn, export_id, [e["site_id"] for e in eventos])
    for ev in eventos:
        ev["hf"] = nombres_ev.get(ev["hfid"])
        ev["asesino"] = nombres_ev.get(ev["slayer_hfid"])
        ev["sitio"] = sitios_ev.get(ev["site_id"])

    victimas = dbmod.all_(
        conn,
        """SELECT e.hfid, e.year, v.name, v.race FROM events e
             LEFT JOIN historical_figures v ON v.export_id = e.export_id AND v.hf_id = e.hfid
            WHERE e.export_id = ? AND e.slayer_hfid = ? ORDER BY e.year""",
        (export_id, hf_id),
    )
    muerte = dbmod.one(
        conn,
        """SELECT event_id, year, slayer_hfid, data_json FROM events
            WHERE export_id = ? AND hfid = ? AND type = 'hf died' ORDER BY year LIMIT 1""",
        (export_id, hf_id),
    )
    if muerte:
        detalles = load_json(muerte.pop("data_json"))
        for clave in ("id", "type", "year", "seconds72", "hfid", "slayer_hfid"):
            detalles.pop(clave, None)
        muerte["detalles"] = {k: v for k, v in detalles.items() if v not in (None, "", [], {})}
        muerte["asesino"] = hf_names(conn, export_id, [muerte["slayer_hfid"]]).get(muerte["slayer_hfid"])

    datos = load_json(fig["data_json"])
    return {
        "id": fig["hf_id"],
        "nombre": fig["name"],
        "raza": fig["race"],
        "casta": fig["caste"],
        "color": color_for(fig["race"] or ""),
        "nacimiento": fig["birth_year"],
        "muerte": fig["death_year"],
        "vive": bool(fig["alive"]),
        "aparecio": fig["appeared"],
        "tipo": fig["associated_type"],
        "banderas": {
            "deidad": bool(fig["is_deity"]),
            "fuerza": bool(fig["is_force"]),
            "fantasma": bool(fig["is_ghost"]),
            "animado": bool(fig["is_animated"]),
            "aventurero": bool(fig["is_adventurer"]),
        },
        "muertes_causadas": fig["kills"],
        "pertenencias": pertenencias,
        "relaciones": relaciones,
        "habilidades": habilidades,
        "esferas": rasgos.get("sphere", []),
        "objetivos": rasgos.get("goal", []),
        "secretos": rasgos.get("secreto", []),
        "interacciones": rasgos.get("interaccion", []),
        "profesiones": rasgos.get("profesion", []),
        "cargos": cargos,
        "sitios": vinculos_sitio,
        "artefactos": artefactos,
        "tramas": tramas,
        "eventos": eventos,
        "eventos_truncados": len(eventos) >= limite_eventos,
        "victimas": victimas,
        "ficha_muerte": muerte,
        "extra": {
            k: v
            for k, v in datos.items()
            if k not in (
                "id", "name", "race", "caste", "birth_year", "birth_seconds",
                "death_year", "death_seconds", "appeared", "associated_type",
                "entity_link", "hf_link", "hf_skill", "sphere", "goal", "site_link",
                "interaction_knowledge", "active_interaction", "intrigue_plot",
            )
        },
    }


@router.get("/exports/{export_id}/artefactos")
def artefactos(
    export_id: int,
    q: Optional[str] = None,
    limite: int = Query(200, le=2000),
    conn: sqlite3.Connection = Conn,
):
    get_export(conn, export_id)
    sql = ["SELECT artifact_id, name, item, item_type, mat, site_id, holder_hfid FROM artifacts WHERE export_id = ?"]
    params: list = [export_id]
    if q:
        sql.append("AND (name LIKE ? OR item LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    sql.append("ORDER BY name LIMIT ?")
    params.append(limite)
    filas = dbmod.all_(conn, " ".join(sql), tuple(params))
    sitios = site_names(conn, export_id, [f["site_id"] for f in filas])
    hfs = hf_names(conn, export_id, [f["holder_hfid"] for f in filas])
    for fila in filas:
        fila["sitio"] = sitios.get(fila["site_id"])
        fila["portador"] = hfs.get(fila["holder_hfid"])
    return {"artefactos": filas}
