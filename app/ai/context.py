"""Seleccion y compactado de los hechos que se le pasan a la IA.

La regla es que la cronica no puede inventarse nada: aqui se recogen solo datos
que están de verdad en la base de datos, y se resumen en un texto corto para que
la llamada a la API sea barata.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Optional

from .. import db as dbmod
from ..api.common import load_json

MAX_EVENTOS = 260

# Tipos de evento que cuentan una historia. El resto (cambios de cargo menores,
# visitas...) se resume por conteo para no gastar contexto.
TIPOS_DESTACADOS = (
    "created site", "site taken over", "destroyed site", "hf destroyed site",
    "hf died", "created artifact", "artifact stored", "artifact lost",
    "attacked site", "razed structure", "field battle", "war peace accepted",
    "entity created", "hf new pet", "hf learns secret", "change hf state",
    "add hf entity link", "remove hf entity link", "hf revived", "hf simple battle event",
    "plundered site", "new site leader", "created structure", "agreement made",
)


def _nombre_sitio(conn, export_id: int, site_id: Optional[int]) -> Optional[str]:
    if site_id is None:
        return None
    fila = dbmod.one(
        conn, "SELECT name FROM sites WHERE export_id = ? AND site_id = ?", (export_id, site_id)
    )
    return fila["name"] if fila else None


def _linea_evento(fila: dict, nombres_hf: dict, nombres_sitio: dict, nombres_ent: dict) -> str:
    partes = [f"{fila['year']}"]
    partes.append(fila["type"] or "evento")
    if fila.get("hfid") is not None:
        partes.append(f"figura={nombres_hf.get(fila['hfid'], fila['hfid'])}")
    if fila.get("slayer_hfid") is not None:
        partes.append(f"causante={nombres_hf.get(fila['slayer_hfid'], fila['slayer_hfid'])}")
    if fila.get("site_id") is not None:
        partes.append(f"lugar={nombres_sitio.get(fila['site_id'], fila['site_id'])}")
    for clave in ("civ_id", "attacker_civ_id", "defender_civ_id"):
        valor = fila.get(clave)
        if valor is not None:
            partes.append(f"{clave}={nombres_ent.get(valor, valor)}")
    detalles = load_json(fila.get("data_json"))
    for clave in ("cause", "state", "reason", "position", "link_type", "artifact_id"):
        if clave in detalles and detalles[clave] not in (None, "", True):
            partes.append(f"{clave}={detalles[clave]}")
    return " | ".join(str(p) for p in partes)


def _decorar(conn: sqlite3.Connection, export_id: int, filas: list[dict]) -> list[str]:
    from ..api.common import hf_names, site_names

    hfs = hf_names(
        conn, export_id,
        [f.get("hfid") for f in filas] + [f.get("slayer_hfid") for f in filas],
    )
    sitios = site_names(conn, export_id, [f.get("site_id") for f in filas])
    ents: dict[int, str] = {}
    for fila in filas:
        for clave in ("civ_id", "attacker_civ_id", "defender_civ_id"):
            valor = fila.get(clave)
            if valor is not None and valor not in ents:
                ents[valor] = ""
    if ents:
        marcas = ",".join("?" * len(ents))
        for row in conn.execute(
            f"SELECT entity_id, name FROM entities WHERE export_id = ? AND entity_id IN ({marcas})",
            (export_id, *ents.keys()),
        ):
            ents[row["entity_id"]] = row["name"]
    return [_linea_evento(f, hfs, sitios, ents) for f in filas]


def contexto_anyos(conn: sqlite3.Connection, export_id: int, desde: int, hasta: int) -> dict:
    marcas = ",".join("?" * len(TIPOS_DESTACADOS))
    filas = dbmod.all_(
        conn,
        f"""SELECT event_id, year, type, site_id, hfid, slayer_hfid, civ_id,
                   attacker_civ_id, defender_civ_id, data_json
              FROM events
             WHERE export_id = ? AND year BETWEEN ? AND ? AND type IN ({marcas})
             ORDER BY year, seconds72 LIMIT ?""",
        (export_id, desde, hasta, *TIPOS_DESTACADOS, MAX_EVENTOS),
    )
    total = conn.execute(
        "SELECT COUNT(*) FROM events WHERE export_id = ? AND year BETWEEN ? AND ?",
        (export_id, desde, hasta),
    ).fetchone()[0]
    resumen_tipos = dbmod.all_(
        conn,
        """SELECT type, COUNT(*) n FROM events WHERE export_id = ? AND year BETWEEN ? AND ?
            GROUP BY type ORDER BY n DESC LIMIT 25""",
        (export_id, desde, hasta),
    )
    guerras = dbmod.all_(
        conn,
        """SELECT name, start_year, end_year FROM event_collections
            WHERE export_id = ? AND LOWER(COALESCE(type,'')) = 'war'
              AND start_year <= ? AND (end_year >= ? OR end_year = -1 OR end_year IS NULL)""",
        (export_id, hasta, desde),
    )
    return {
        "titulo": f"Crónica de los anyos {desde} a {hasta}",
        "hechos": _decorar(conn, export_id, filas),
        "eventos_totales": total,
        "eventos_incluidos": len(filas),
        "tipos": resumen_tipos,
        "guerras": guerras,
    }


def contexto_figura(conn: sqlite3.Connection, export_id: int, hf_id: int) -> dict:
    fig = dbmod.one(
        conn,
        """SELECT hf_id, name, race, caste, birth_year, death_year, alive,
                  associated_type, kills FROM historical_figures
            WHERE export_id = ? AND hf_id = ?""",
        (export_id, hf_id),
    )
    if fig is None:
        return {}
    filas = dbmod.all_(
        conn,
        """SELECT event_id, year, type, site_id, hfid, slayer_hfid, civ_id,
                  attacker_civ_id, defender_civ_id, data_json
             FROM events WHERE export_id = ? AND (hfid = ? OR slayer_hfid = ?)
             ORDER BY year, seconds72 LIMIT ?""",
        (export_id, hf_id, hf_id, MAX_EVENTOS),
    )
    entidades = dbmod.all_(
        conn,
        """SELECT e.name, l.link_type, l.former FROM hf_entity_links l
             LEFT JOIN entities e ON e.export_id = l.export_id AND e.entity_id = l.entity_id
            WHERE l.export_id = ? AND l.hf_id = ?""",
        (export_id, hf_id),
    )
    rasgos = dbmod.all_(
        conn, "SELECT kind, value FROM hf_traits WHERE export_id = ? AND hf_id = ?", (export_id, hf_id)
    )
    habilidades = dbmod.all_(
        conn,
        "SELECT skill, total_ip FROM hf_skills WHERE export_id = ? AND hf_id = ? ORDER BY total_ip DESC LIMIT 12",
        (export_id, hf_id),
    )
    return {
        "titulo": f"Vida de {fig['name']}",
        "ficha": fig,
        "entidades": entidades,
        "rasgos": rasgos,
        "habilidades": habilidades,
        "hechos": _decorar(conn, export_id, filas),
        "eventos_incluidos": len(filas),
    }


def contexto_fortaleza(conn: sqlite3.Connection, export_id: int, site_id: int) -> dict:
    from ..model import fortress as F

    resumen = F.summary(conn, export_id, site_id)
    filas = dbmod.all_(
        conn,
        """SELECT event_id, year, type, site_id, hfid, slayer_hfid, civ_id,
                  attacker_civ_id, defender_civ_id, data_json
             FROM events WHERE export_id = ? AND site_id = ?
             ORDER BY year, seconds72 LIMIT ?""",
        (export_id, site_id, MAX_EVENTOS),
    )
    nombre = (resumen.get("sitio") or {}).get("nombre") or f"sitio {site_id}"
    return {
        "titulo": f"Crónica de {nombre}",
        "ficha": resumen.get("sitio"),
        "fundacion": resumen.get("fundacion"),
        "civilizacion": resumen.get("civilizacion"),
        "habitantes": {
            k: v for k, v in (resumen.get("habitantes") or {}).items()
            if k in ("total", "vivos", "muertos")
        },
        "artefactos": [a["name"] for a in (resumen.get("artefactos") or {}).get("en_el_sitio", [])],
        "hechos": _decorar(conn, export_id, filas),
        "eventos_incluidos": len(filas),
    }


def construir(conn: sqlite3.Connection, export_id: int, ambito: dict) -> dict:
    tipo = ambito.get("tipo")
    if tipo == "anyos":
        return contexto_anyos(conn, export_id, int(ambito["desde"]), int(ambito["hasta"]))
    if tipo == "figura":
        return contexto_figura(conn, export_id, int(ambito["hf_id"]))
    if tipo == "fortaleza":
        return contexto_fortaleza(conn, export_id, int(ambito["site_id"]))
    return {}


def a_texto(contexto: dict) -> str:
    """Convierte el contexto en el bloque de datos que ve el modelo."""
    lineas = [f"# {contexto.get('titulo', 'Crónica')}", ""]
    for clave in ("ficha", "civilizacion", "habitantes"):
        if contexto.get(clave):
            lineas.append(f"{clave}: {contexto[clave]}")
    if contexto.get("fundacion") is not None:
        lineas.append(f"fundacion: {contexto['fundacion']}")
    if contexto.get("entidades"):
        lineas.append(f"entidades: {contexto['entidades']}")
    if contexto.get("rasgos"):
        lineas.append(f"rasgos: {contexto['rasgos']}")
    if contexto.get("habilidades"):
        lineas.append(f"habilidades: {contexto['habilidades']}")
    if contexto.get("artefactos"):
        lineas.append(f"artefactos: {contexto['artefactos']}")
    if contexto.get("guerras"):
        lineas.append(f"guerras: {contexto['guerras']}")
    if contexto.get("tipos"):
        lineas.append(f"recuento de tipos de evento: {contexto['tipos']}")
    if contexto.get("eventos_totales") is not None:
        lineas.append(
            f"eventos totales en el ámbito: {contexto['eventos_totales']} "
            f"(se listan {contexto.get('eventos_incluidos', 0)})"
        )
    lineas.append("")
    lineas.append("## Hechos registrados (anyo | tipo | detalles)")
    lineas.extend(contexto.get("hechos", []))
    return "\n".join(lineas)


def huella(texto: str, modelo: str) -> str:
    return hashlib.sha1(f"{modelo}\n{texto}".encode("utf-8")).hexdigest()
