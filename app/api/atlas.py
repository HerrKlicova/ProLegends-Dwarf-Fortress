"""Mapa del mundo, fichas de sitio y fichas de entidad."""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Query

from .. import db as dbmod
from ..errors import NotFoundError
from ..model import diccionario as D
from ..parser import legends as L
from . import common
from .common import (
    Conn,
    color_de,
    color_for,
    entity_index,
    event_payload,
    get_export,
    hf_names,
    load_json,
    site_names,
)

router = APIRouter(tags=["atlas"])


@router.get("/exports/{export_id}/mapa")
def mapa(export_id: int, conn: sqlite3.Connection = Conn):
    """Todo lo que el mapa necesita, de una vez.

    Se manda el historico completo de propiedad para que el deslizador de anyo
    funcione en el navegador sin volver a preguntar al servidor en cada paso.
    """
    exp = get_export(conn, export_id)
    entidades = entity_index(conn, export_id)

    sitios = []
    for row in dbmod.all_(
        conn,
        """SELECT site_id, name, type, coord_x, coord_y, civ_id, cur_owner_id,
                  owner_id, root_civ_id, state, founded_year
             FROM sites WHERE export_id = ? ORDER BY site_id""",
        (export_id,),
    ):
        sitios.append(
            {
                "id": row["site_id"],
                "nombre": row["name"],
                "tipo": row["type"],
                "capa": L.site_layer(row["type"]),
                "x": row["coord_x"],
                "y": row["coord_y"],
                "civ_id": row["civ_id"],
                "propietario_actual": row["owner_id"],
                "civ_raiz": row["root_civ_id"],
                "estado": row["state"],
                "fundado": row["founded_year"],
            }
        )

    propiedad = [
        [r["site_id"], r["year"], r["owner_entity_id"], r["state"]]
        for r in conn.execute(
            """SELECT site_id, year, owner_entity_id, state FROM site_ownership
                WHERE export_id = ? ORDER BY year, seconds72, rowid""",
            (export_id,),
        )
    ]

    # Facciones: entidades que poseen o han poseido algún sitio, más sus raíces.
    usadas = {p[2] for p in propiedad if p[2] is not None}
    usadas |= {s["propietario_actual"] for s in sitios if s["propietario_actual"] is not None}
    raices = {entidades[e]["root_id"] for e in usadas if e in entidades}
    facciones = []
    for eid in sorted(usadas | {r for r in raices if r is not None}):
        ent = entidades.get(eid)
        if ent is None:
            continue
        facciones.append(
            {
                "id": eid,
                "nombre": ent["name"],
                "tipo": ent["type"],
        "tipo_legible": D.entidad(ent["type"]),
                "raza": D.raza(ent["race"]),
                "raiz": ent["root_id"],
                "color": ent["color"],
            }
        )

    return {
        "export": {
            "id": exp["id"],
            "prefix": exp["prefix"],
            "ancho": exp["world_width"],
            "alto": exp["world_height"],
            "anyo_min": exp["min_year"],
            "anyo_max": exp["max_year"],
            "fecha_partida": exp["game_year"],
        },
        "sitios": sitios,
        "propiedad": propiedad,
        "facciones": facciones,
        "bestias": _bestias(conn, export_id),
        "razas": _razas(conn, export_id),
    }


def _razas(conn: sqlite3.Connection, export_id: int) -> list[dict]:
    filas = dbmod.all_(
        conn,
        """SELECT race, COUNT(*) n FROM entities
            WHERE export_id = ? AND race IS NOT NULL AND race <> ''
            GROUP BY race ORDER BY n DESC""",
        (export_id,),
    )
    return [{"raza": D.raza(f["race"]), "codigo_raza": f["race"], "entidades": f["n"], "color": color_de(conn, export_id, f["race"])} for f in filas]


def _bestias(conn: sqlite3.Connection, export_id: int) -> list[dict]:
    """Figuras que no pertenecen a una civilizacion y andan sueltas por el mapa.

    Se incluye el rastro de posiciones (anyo, sitio) sacado de los eventos, para
    que el deslizador pueda mostrar donde estaban en cada momento.
    """
    tipos = tuple(sorted(L.BEAST_TYPES))
    marcas = ",".join("?" * len(tipos))
    figuras = dbmod.all_(
        conn,
        f"""SELECT hf_id, name, race, associated_type, birth_year, death_year, alive
              FROM historical_figures
             WHERE export_id = ? AND LOWER(COALESCE(associated_type,'')) IN ({marcas})""",
        (export_id, *tipos),
    )
    if not figuras:
        return []
    ids = [f["hf_id"] for f in figuras]
    rastro: dict[int, list] = {i: [] for i in ids}
    marcas_ids = ",".join("?" * len(ids))
    # Dos consultas separadas en lugar de un OR: así cada una usa su indice.
    for columna in ("hfid", "slayer_hfid"):
        # Ojo: el filtro de site_id se hace en Python. Si se pone en el SQL,
        # SQLite prefiere el indice por sitio y deja de usar el de figura.
        for row in conn.execute(
            f"""SELECT {columna} AS quien, year, site_id FROM events
                 WHERE export_id = ? AND {columna} IN ({marcas_ids})""",
            (export_id, *ids),
        ):
            if row["site_id"] is not None and row["quien"] in rastro:
                rastro[row["quien"]].append([row["year"], row["site_id"]])
    for lista in rastro.values():
        lista.sort(key=lambda par: par[0] if par[0] is not None else 0)
    # Además, el sitio con el que la figura tiene vinculo explicito.
    for row in conn.execute(
        f"""SELECT hf_id, site_id FROM hf_site_links
             WHERE export_id = ? AND hf_id IN ({marcas_ids}) AND site_id IS NOT NULL""",
        (export_id, *ids),
    ):
        rastro.setdefault(row["hf_id"], [])
        rastro[row["hf_id"]].insert(0, [-1, row["site_id"]])

    salida = []
    for fig in figuras:
        pistas = rastro.get(fig["hf_id"], [])[:60]
        if not pistas:
            continue
        salida.append(
            {
                "hf_id": fig["hf_id"],
                "nombre": fig["name"],
                "raza": D.raza(fig["race"]),
                "tipo": D.tipo_figura(fig["associated_type"]),
                "nacimiento": fig["birth_year"],
                "muerte": fig["death_year"],
                "vive": bool(fig["alive"]),
                "posiciones": pistas,
                "color": color_de(conn, export_id, fig["race"], fig["associated_type"] or ""),
            }
        )
    return salida


@router.get("/exports/{export_id}/terreno")
def terreno_del_mundo(export_id: int, conn: sqlite3.Connection = Conn):
    """La geografía: rejilla de biomas, ríos, calzadas y picos con nombre.

    Va aparte del mapa porque no cambia con el año: se pide una vez, se dibuja
    una vez y el deslizador solo repinta lo que sí cambia (los sitios y quién
    los posee).
    """
    from ..model import terreno as modelo

    get_export(conn, export_id)
    return modelo.terreno(conn, export_id)


@router.get("/exports/{export_id}/geografia")
def informe_geografia(export_id: int, conn: sqlite3.Connection = Conn):
    """Qué trae este export sobre el mapa, tal y como viene.

    Sirve para resolver dudas del mapa sin suponer nada: se mira el dato en vez
    de imaginárselo. Se prefieren los XML, que es la fuente; si ya no están a
    mano se saca de la base de datos, que dice lo mismo con otras palabras.
    """
    from pathlib import Path

    from .. import config
    from ..parser.discover import discover
    from ..parser.inspeccion import informe, informe_bd, informe_datos

    exp = get_export(conn, export_id)

    texto = ""
    origen = ""
    try:
        pares, _ = discover(config.IMPORTS_DIR)
        par = next((p for p in pares if p.prefix == exp["prefix"]), None)
        if par is not None:
            rutas = [r for r in (par.main, par.plus) if r and Path(r).exists()]
            if rutas:
                texto = informe(rutas)
                origen = "los ficheros XML"
    except Exception:  # pragma: no cover - si falla, queda la base de datos
        texto = ""

    if not texto:
        texto = informe_bd(conn, export_id)
        origen = "la base de datos (los XML ya no estaban en su carpeta)"

    # Lo del mapa sale del XML si está; los sucesos, los vínculos y las razas
    # salen siempre de la base de datos, que es donde se ve si ProLegends sabe
    # contarlos o se le escapan.
    try:
        texto += "\n" + informe_datos(conn, export_id)
    except Exception:  # pragma: no cover - el informe del mapa vale igual
        pass

    fichero = ""
    try:
        config.ensure_dirs()
        destino = config.DATA_DIR / f"informe-{exp['prefix']}.txt"
        destino.write_text(texto, encoding="utf-8")
        fichero = str(destino)
    except OSError:
        pass

    return {"texto": texto, "origen": origen, "fichero": fichero}


@router.get("/exports/{export_id}/sitios/{site_id}")
def ficha_sitio(export_id: int, site_id: int, limite_eventos: int = 400,
                conn: sqlite3.Connection = Conn):
    get_export(conn, export_id)
    sitio = dbmod.one(
        conn, "SELECT * FROM sites WHERE export_id = ? AND site_id = ?", (export_id, site_id)
    )
    if sitio is None:
        raise NotFoundError(f"No hay ningún sitio con el número {site_id} en este export.")

    entidades = entity_index(conn, export_id)

    propietarios = []
    for row in conn.execute(
        """SELECT year, owner_entity_id, state, event_type, source FROM site_ownership
            WHERE export_id = ? AND site_id = ? ORDER BY year, seconds72, rowid""",
        (export_id, site_id),
    ):
        ent = entidades.get(row["owner_entity_id"]) if row["owner_entity_id"] is not None else None
        propietarios.append(
            {
                "anyo": row["year"],
                "entidad_id": row["owner_entity_id"],
                "entidad": ent["name"] if ent else None,
                "raza": D.raza(ent["race"]) if ent else None,
                "color": ent["color"] if ent else None,
                "estado": row["state"],
                "evento": row["event_type"],
                "origen": row["source"],
            }
        )

    eventos_raw = dbmod.all_(
        conn,
        """SELECT * FROM events WHERE export_id = ? AND site_id = ?
            ORDER BY year, seconds72 LIMIT ?""",
        (export_id, site_id, limite_eventos),
    )
    eventos = common.narrar(conn, export_id, eventos_raw,
                            [event_payload(e) for e in eventos_raw])
    nombres_hf = hf_names(
        conn, export_id, [e["hfid"] for e in eventos] + [e["slayer_hfid"] for e in eventos]
    )
    for ev in eventos:
        ev["hf"] = nombres_hf.get(ev["hfid"])
        ev["asesino"] = nombres_hf.get(ev["slayer_hfid"])

    estructuras = dbmod.all_(
        conn,
        """SELECT structure_id, name, type, subtype FROM site_structures
            WHERE export_id = ? AND site_id = ? ORDER BY structure_id""",
        (export_id, site_id),
    )
    for e in estructuras:
        e["tipo_legible"] = D.estructura(e["type"])
    artefactos = dbmod.all_(
        conn,
        "SELECT artifact_id, name, item FROM artifacts WHERE export_id = ? AND site_id = ?",
        (export_id, site_id),
    )
    habitantes = dbmod.all_(
        conn,
        """SELECT h.hf_id, h.name, h.race, h.alive, l.link_type
             FROM hf_site_links l JOIN historical_figures h
               ON h.export_id = l.export_id AND h.hf_id = l.hf_id
            WHERE l.export_id = ? AND l.site_id = ?
            ORDER BY h.alive DESC, h.name LIMIT 400""",
        (export_id, site_id),
    )
    common.traducir_razas(habitantes)
    for h in habitantes:
        h["vinculo_legible"] = D.vinculo_sitio(h["link_type"])

    ent_actual = entidades.get(sitio["owner_id"])
    return {
        "id": sitio["site_id"],
        "nombre": sitio["name"],
        "tipo": sitio["type"],
        "tipo_legible": D.sitio(sitio["type"]),
        "capa": L.site_layer(sitio["type"]),
        "coordenadas": {"x": sitio["coord_x"], "y": sitio["coord_y"]},
        "rectangulo": sitio["rectangle"],
        "estado": sitio["state"],
        "fundado": sitio["founded_year"],
        "propietario": {
            "id": sitio["owner_id"],
            "nombre": ent_actual["name"] if ent_actual else None,
            "raza": D.raza(ent_actual["race"]) if ent_actual else None,
            "color": ent_actual["color"] if ent_actual else None,
        },
        "civilizacion": (
            {
                "id": sitio["root_civ_id"],
                "nombre": entidades[sitio["root_civ_id"]]["name"],
                "raza": D.raza(entidades[sitio["root_civ_id"]]["race"]),
            }
            if sitio["root_civ_id"] in entidades
            else None
        ),
        "propietarios": propietarios,
        "estructuras": estructuras,
        "artefactos": artefactos,
        "habitantes": habitantes,
        "eventos": eventos,
        "eventos_truncados": len(eventos) >= limite_eventos,
    }


@router.get("/exports/{export_id}/entidades")
def listar_entidades(
    export_id: int,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
    limite: int = Query(200, le=2000),
    conn: sqlite3.Connection = Conn,
):
    get_export(conn, export_id)
    sql = ["SELECT entity_id, name, type, race, parent_id, root_id, depth FROM entities WHERE export_id = ?"]
    params: list = [export_id]
    if tipo:
        sql.append("AND type = ?")
        params.append(tipo)
    if q:
        sql.append("AND name LIKE ?")
        params.append(f"%{q}%")
    sql.append("ORDER BY depth, name LIMIT ?")
    params.append(limite)
    filas = dbmod.all_(conn, " ".join(sql), tuple(params))
    for fila in filas:
        fila["color"] = color_de(conn, export_id, fila["race"], fila["name"] or "")
    common.traducir_razas(filas)
    return {"entidades": filas}


@router.get("/exports/{export_id}/entidades/{entity_id}")
def ficha_entidad(export_id: int, entity_id: int, conn: sqlite3.Connection = Conn):
    get_export(conn, export_id)
    ent = dbmod.one(
        conn, "SELECT * FROM entities WHERE export_id = ? AND entity_id = ?", (export_id, entity_id)
    )
    if ent is None:
        raise NotFoundError(f"No hay ninguna entidad con el número {entity_id}.")
    entidades = entity_index(conn, export_id)
    hijos = dbmod.all_(
        conn,
        """SELECT e.entity_id, e.name, e.type, e.race FROM entity_children c
             JOIN entities e ON e.export_id = c.export_id AND e.entity_id = c.child_id
            WHERE c.export_id = ? AND c.parent_id = ? ORDER BY e.name""",
        (export_id, entity_id),
    )
    common.traducir_razas(hijos)
    sitios = dbmod.all_(
        conn,
        """SELECT s.site_id, s.name, s.type, s.coord_x, s.coord_y, s.state
             FROM sites s WHERE s.export_id = ? AND (s.owner_id = ? OR s.root_civ_id = ?)
            ORDER BY s.name LIMIT 500""",
        (export_id, entity_id, entity_id),
    )
    cargos = dbmod.all_(
        conn,
        """SELECT p.position_id, p.name, a.hfid, h.name AS titular
             FROM entity_positions p
             LEFT JOIN entity_position_assignments a
                    ON a.export_id = p.export_id AND a.entity_id = p.entity_id
                   AND a.position_id = p.position_id
             LEFT JOIN historical_figures h
                    ON h.export_id = p.export_id AND h.hf_id = a.hfid
            WHERE p.export_id = ? AND p.entity_id = ? ORDER BY p.position_id""",
        (export_id, entity_id),
    )
    guerras = dbmod.all_(
        conn,
        """SELECT collection_id, type, name, start_year, end_year,
                  attacking_enid, defending_enid
             FROM event_collections
            WHERE export_id = ? AND (attacking_enid = ? OR defending_enid = ?)
            ORDER BY start_year""",
        (export_id, entity_id, entity_id),
    )
    for guerra in guerras:
        for lado in ("attacking_enid", "defending_enid"):
            otro = entidades.get(guerra[lado])
            guerra[lado.replace("_enid", "_nombre")] = otro["name"] if otro else None
    miembros = dbmod.all_(
        conn,
        """SELECT h.hf_id, h.name, h.race, h.alive, l.link_type
             FROM hf_entity_links l JOIN historical_figures h
               ON h.export_id = l.export_id AND h.hf_id = l.hf_id
            WHERE l.export_id = ? AND l.entity_id = ?
            ORDER BY h.alive DESC, h.name LIMIT 300""",
        (export_id, entity_id),
    )
    common.traducir_razas(miembros)
    for m in miembros:
        m["vinculo_legible"] = D.vinculo_ent(m["link_type"])
    padre = entidades.get(ent["parent_id"]) if ent["parent_id"] is not None else None
    raiz = entidades.get(ent["root_id"]) if ent["root_id"] is not None else None
    return {
        "id": ent["entity_id"],
        "nombre": ent["name"],
        "tipo": ent["type"],
        "raza": D.raza(ent["race"]),
        "color": color_de(conn, export_id, ent["race"], ent["name"] or ""),
        "padre": {"id": padre["entity_id"], "nombre": padre["name"]} if padre else None,
        "raiz": {"id": raiz["entity_id"], "nombre": raiz["name"]} if raiz else None,
        "hijos": hijos,
        "sitios": sitios,
        "cargos": cargos,
        "guerras": guerras,
        "miembros": miembros,
        "extra": {
            k: v
            for k, v in load_json(ent["data_json"]).items()
            if k not in ("id", "name", "type", "race", "child", "entity_position",
                         "entity_position_assignment", "site_link")
        },
    }


@router.get("/exports/{export_id}/colecciones")
def listar_colecciones(
    export_id: int,
    tipo: Optional[str] = None,
    limite: int = Query(300, le=3000),
    conn: sqlite3.Connection = Conn,
):
    """Guerras, batallas, saqueos... tal como los agrupa el propio XML."""
    get_export(conn, export_id)
    sql = ["SELECT collection_id, type, name, start_year, end_year, site_id, attacking_enid, defending_enid FROM event_collections WHERE export_id = ?"]
    params: list = [export_id]
    if tipo:
        sql.append("AND type = ?")
        params.append(tipo)
    sql.append("ORDER BY start_year DESC LIMIT ?")
    params.append(limite)
    filas = dbmod.all_(conn, " ".join(sql), tuple(params))
    entidades = entity_index(conn, export_id)
    nombres = site_names(conn, export_id, [f["site_id"] for f in filas])
    for fila in filas:
        fila["tipo_legible"] = D.coleccion(fila["type"])
        fila["sitio"] = nombres.get(fila["site_id"])
        for lado in ("attacking_enid", "defending_enid"):
            ent = entidades.get(fila[lado])
            fila[lado.replace("_enid", "_nombre")] = ent["name"] if ent else None
    tipos = dbmod.all_(
        conn,
        "SELECT type, COUNT(*) n FROM event_collections WHERE export_id = ? GROUP BY type ORDER BY n DESC",
        (export_id,),
    )
    for t in tipos:
        t["legible"] = D.coleccion(t["type"])
    return {"colecciones": filas, "tipos": tipos}
