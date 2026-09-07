"""Deteccion y analisis de la fortaleza del jugador.

DF no marca en ninguna parte cual es "tu" fortaleza, asi que hay que deducirla:

  - un sitio que aparece en un export y no existia en el anterior del mismo
    mundo, o
  - un sitio cuyo gobierno se creo en el anyo mas reciente del mundo.

Si queda duda, se ofrece la lista de candidatos para elegir a mano una sola vez;
la eleccion se guarda y manda por encima de la deteccion automatica.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .. import db as dbmod
from ..parser import legends as L

# Palabras que aparecen en los tipos de evento de DF. Son vocabulario del juego,
# no de un mundo concreto.
ATAQUE = ("attacked", "siege", "razed", "destroyed", "pillage", "plundered", "raid",
          "beast attack", "insurrection", "occupation")
LLEGADA = ("arrived", "migrat", "refugee", "settled")
COMERCIO = ("merchant", "trade", "caravan")
RECLAMACION = ("claim", "reclaim")
CREACION_ARTEFACTO = ("created artifact", "artifact created")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _exports(conn: sqlite3.Connection, world_id: int) -> list[dict]:
    return dbmod.all_(
        conn,
        """SELECT * FROM exports WHERE world_id = ? AND status = 'ok'
            ORDER BY COALESCE(game_year,0), COALESCE(game_month,0), COALESCE(game_day,0), id""",
        (world_id,),
    )


# --------------------------------------------------------------- deteccion
def candidates(conn: sqlite3.Connection, world_id: int) -> dict:
    exports = _exports(conn, world_id)
    if not exports:
        return {"candidatos": [], "export_id": None, "export_anterior": None}

    actual = exports[-1]
    anterior = exports[-2] if len(exports) > 1 else None

    sitios = dbmod.all_(
        conn,
        """SELECT site_id, name, type, coord_x, coord_y, owner_id, root_civ_id,
                  state, founded_year
             FROM sites WHERE export_id = ?""",
        (actual["id"],),
    )
    if not sitios:
        return {"candidatos": [], "export_id": actual["id"],
                "export_anterior": anterior["id"] if anterior else None}

    previos: set[int] = set()
    if anterior:
        previos = {
            r["site_id"]
            for r in conn.execute(
                "SELECT site_id FROM sites WHERE export_id = ?", (anterior["id"],)
            )
        }

    fundaciones = [s["founded_year"] for s in sitios if s["founded_year"] is not None]
    ultima_fundacion = max(fundaciones) if fundaciones else None

    marcados = []
    for sitio in sitios:
        puntos = 0
        razones: list[str] = []
        if anterior and sitio["site_id"] not in previos:
            puntos += 100
            razones.append(f"no existia en el export anterior ({anterior['prefix']})")
        if ultima_fundacion is not None and sitio["founded_year"] == ultima_fundacion:
            puntos += 50
            razones.append(f"su gobierno se creo en el anyo mas reciente ({ultima_fundacion})")
        elif (
            ultima_fundacion is not None
            and sitio["founded_year"] is not None
            and sitio["founded_year"] >= ultima_fundacion - 5
        ):
            puntos += 15
            razones.append(f"fundado hace poco (anyo {sitio['founded_year']})")
        if puntos and sitio["state"] == L.STATE_RUINS:
            puntos -= 40
            razones.append("esta en ruinas")
        if puntos <= 0:
            continue
        marcados.append(
            {
                "site_id": sitio["site_id"],
                "nombre": sitio["name"],
                "tipo": sitio["type"],
                "x": sitio["coord_x"],
                "y": sitio["coord_y"],
                "fundado": sitio["founded_year"],
                "puntuacion": puntos,
                "razones": razones,
            }
        )

    marcados.sort(key=lambda c: (-c["puntuacion"], c["nombre"] or ""))
    return {
        "candidatos": marcados,
        "export_id": actual["id"],
        "export_anterior": anterior["id"] if anterior else None,
    }


def resolve(conn: sqlite3.Connection, world_id: int) -> dict:
    """Devuelve la fortaleza elegida, o la duda si hay varias posibles."""
    info = candidates(conn, world_id)
    manual = dbmod.one(
        conn, "SELECT site_id FROM fortress_choice WHERE world_id = ?", (world_id,)
    )
    if manual:
        return {
            "site_id": manual["site_id"],
            "origen": "manual",
            "ambiguo": False,
            "candidatos": info["candidatos"],
            "export_id": info["export_id"],
            "export_anterior": info["export_anterior"],
        }
    candidatos = info["candidatos"]
    if not candidatos:
        return {"site_id": None, "origen": "sin_candidatos", "ambiguo": False, **info}
    mejor = candidatos[0]
    ambiguo = len(candidatos) > 1 and candidatos[1]["puntuacion"] == mejor["puntuacion"]
    return {
        "site_id": None if ambiguo else mejor["site_id"],
        "origen": "ambiguo" if ambiguo else "automatico",
        "ambiguo": ambiguo,
        "candidatos": candidatos,
        "export_id": info["export_id"],
        "export_anterior": info["export_anterior"],
    }


def choose(conn: sqlite3.Connection, world_id: int, site_id: int) -> None:
    conn.execute(
        """INSERT INTO fortress_choice (world_id, site_id, chosen_by, updated_at)
           VALUES (?,?,'manual',?)
           ON CONFLICT(world_id) DO UPDATE SET site_id = excluded.site_id,
                                               chosen_by = 'manual',
                                               updated_at = excluded.updated_at""",
        (world_id, site_id, _now()),
    )


def forget(conn: sqlite3.Connection, world_id: int) -> None:
    conn.execute("DELETE FROM fortress_choice WHERE world_id = ?", (world_id,))


# ----------------------------------------------------------------- resumen
def _tipo_en(tipo: Optional[str], palabras: tuple[str, ...]) -> bool:
    t = (tipo or "").lower()
    return any(p in t for p in palabras)


def summary(conn: sqlite3.Connection, export_id: int, site_id: int) -> dict:
    sitio = dbmod.one(
        conn, "SELECT * FROM sites WHERE export_id = ? AND site_id = ?", (export_id, site_id)
    )
    if sitio is None:
        return {}

    propietario = dbmod.one(
        conn,
        "SELECT entity_id, name, type, race, root_id FROM entities WHERE export_id = ? AND entity_id = ?",
        (export_id, sitio["owner_id"]),
    )
    civilizacion = dbmod.one(
        conn,
        "SELECT entity_id, name, race FROM entities WHERE export_id = ? AND entity_id = ?",
        (export_id, sitio["root_civ_id"]),
    )

    habitantes = dbmod.all_(
        conn,
        """SELECT h.hf_id, h.name, h.race, h.alive, h.death_year, l.link_type
             FROM hf_site_links l JOIN historical_figures h
               ON h.export_id = l.export_id AND h.hf_id = l.hf_id
            WHERE l.export_id = ? AND l.site_id = ?""",
        (export_id, site_id),
    )
    vivos = [h for h in habitantes if h["alive"]]
    muertos = [h for h in habitantes if not h["alive"]]

    censo = []
    if civilizacion:
        censo = dbmod.all_(
            conn,
            "SELECT race, count FROM entity_populations WHERE export_id = ? AND civ_id = ?",
            (export_id, civilizacion["entity_id"]),
        )

    artefactos = dbmod.all_(
        conn,
        """SELECT artifact_id, name, item, holder_hfid FROM artifacts
            WHERE export_id = ? AND site_id = ?""",
        (export_id, site_id),
    )
    creados = dbmod.all_(
        conn,
        """SELECT e.event_id, e.year, e.artifact_id, a.name, e.hfid, h.name AS autor
             FROM events e
             LEFT JOIN artifacts a ON a.export_id = e.export_id AND a.artifact_id = e.artifact_id
             LEFT JOIN historical_figures h ON h.export_id = e.export_id AND h.hf_id = e.hfid
            WHERE e.export_id = ? AND e.site_id = ? AND e.type IN ('created artifact')
            ORDER BY e.year""",
        (export_id, site_id),
    )

    eventos_sitio = dbmod.all_(
        conn,
        """SELECT event_id, year, type, data_json, hfid, attacker_civ_id, defender_civ_id
             FROM events WHERE export_id = ? AND site_id = ? ORDER BY year, seconds72""",
        (export_id, site_id),
    )
    caravanas = [e for e in eventos_sitio if _tipo_en(e["type"], COMERCIO)]
    ataques = [e for e in eventos_sitio if _tipo_en(e["type"], ATAQUE)]
    llegadas = [e for e in eventos_sitio if _tipo_en(e["type"], LLEGADA)]

    from ..api.common import load_json

    def limpiar(filas: list[dict]) -> list[dict]:
        salida = []
        for fila in filas:
            detalles = load_json(fila.get("data_json"))
            for clave in ("id", "type", "year", "seconds72"):
                detalles.pop(clave, None)
            salida.append(
                {
                    "id": fila["event_id"],
                    "anyo": fila["year"],
                    "tipo": fila["type"],
                    "detalles": {k: v for k, v in detalles.items() if v not in (None, "", [], {})},
                }
            )
        return salida

    return {
        "sitio": {
            "id": sitio["site_id"],
            "nombre": sitio["name"],
            "tipo": sitio["type"],
            "x": sitio["coord_x"],
            "y": sitio["coord_y"],
            "estado": sitio["state"],
        },
        "fundacion": sitio["founded_year"],
        "propietario": propietario,
        "civilizacion": civilizacion,
        "censo_civilizacion": censo,
        "habitantes": {
            "total": len(habitantes),
            "vivos": len(vivos),
            "muertos": len(muertos),
            "lista_vivos": sorted(vivos, key=lambda h: h["name"] or "")[:200],
            "lista_muertos": sorted(muertos, key=lambda h: h["death_year"] or 0, reverse=True)[:200],
        },
        "artefactos": {"en_el_sitio": artefactos, "creados_aqui": creados},
        "caravanas": limpiar(caravanas),
        "ataques": limpiar(ataques),
        "llegadas": limpiar(llegadas),
        "eventos_totales": len(eventos_sitio),
    }


# -------------------------------------------------------------------- diff
def diff(
    conn: sqlite3.Connection,
    export_desde: int,
    export_hasta: int,
    site_id: Optional[int] = None,
    radio: int = 20,
) -> dict:
    """Que ha cambiado entre dos exports del mismo mundo."""
    from ..api.common import load_json

    ids_antes = {
        r[0] for r in conn.execute(
            "SELECT event_id FROM events WHERE export_id = ?", (export_desde,)
        )
    }
    sitios_antes = {
        r[0] for r in conn.execute(
            "SELECT site_id FROM sites WHERE export_id = ?", (export_desde,)
        )
    }
    art_antes = {
        r[0] for r in conn.execute(
            "SELECT artifact_id FROM artifacts WHERE export_id = ?", (export_desde,)
        )
    }
    vivos_antes = {
        r[0] for r in conn.execute(
            "SELECT hf_id FROM historical_figures WHERE export_id = ? AND alive = 1", (export_desde,)
        )
    }

    # Coordenadas de mi fortaleza para medir cercania.
    fx = fy = None
    if site_id is not None:
        fila = dbmod.one(
            conn,
            "SELECT coord_x, coord_y FROM sites WHERE export_id = ? AND site_id = ?",
            (export_hasta, site_id),
        )
        if fila:
            fx, fy = fila["coord_x"], fila["coord_y"]

    coords = {
        r["site_id"]: (r["coord_x"], r["coord_y"], r["name"])
        for r in conn.execute(
            "SELECT site_id, coord_x, coord_y, name FROM sites WHERE export_id = ?", (export_hasta,)
        )
    }

    def distancia(sid: Optional[int]) -> Optional[int]:
        if sid is None or fx is None or sid not in coords:
            return None
        x, y, _ = coords[sid]
        if x is None or y is None:
            return None
        return max(abs(x - fx), abs(y - fy))

    nuevos_eventos = []
    for row in conn.execute(
        """SELECT event_id, year, type, site_id, hfid, slayer_hfid, artifact_id,
                  attacker_civ_id, defender_civ_id, civ_id, data_json
             FROM events WHERE export_id = ? ORDER BY year, seconds72""",
        (export_hasta,),
    ):
        if row["event_id"] in ids_antes:
            continue
        detalles = load_json(row["data_json"])
        for clave in ("id", "type", "year", "seconds72"):
            detalles.pop(clave, None)
        dist = distancia(row["site_id"])
        nuevos_eventos.append(
            {
                "id": row["event_id"],
                "anyo": row["year"],
                "tipo": row["type"],
                "site_id": row["site_id"],
                "sitio": coords.get(row["site_id"], (None, None, None))[2],
                "hfid": row["hfid"],
                "slayer_hfid": row["slayer_hfid"],
                "artifact_id": row["artifact_id"],
                "distancia": dist,
                "en_mi_fortaleza": site_id is not None and row["site_id"] == site_id,
                "cerca": dist is not None and dist <= radio,
                "detalles": {k: v for k, v in detalles.items() if v not in (None, "", [], {})},
            }
        )

    nuevos_sitios = dbmod.all_(
        conn,
        "SELECT site_id, name, type, coord_x, coord_y FROM sites WHERE export_id = ?",
        (export_hasta,),
    )
    nuevos_sitios = [s for s in nuevos_sitios if s["site_id"] not in sitios_antes]
    for s in nuevos_sitios:
        s["distancia"] = distancia(s["site_id"])

    nuevos_artefactos = dbmod.all_(
        conn,
        """SELECT artifact_id, name, item, site_id, holder_hfid FROM artifacts
            WHERE export_id = ?""",
        (export_hasta,),
    )
    nuevos_artefactos = [a for a in nuevos_artefactos if a["artifact_id"] not in art_antes]
    for a in nuevos_artefactos:
        a["sitio"] = coords.get(a["site_id"], (None, None, None))[2]
        a["mio"] = site_id is not None and a["site_id"] == site_id

    nuevas_muertes = dbmod.all_(
        conn,
        """SELECT hf_id, name, race, death_year, associated_type FROM historical_figures
            WHERE export_id = ? AND alive = 0""",
        (export_hasta,),
    )
    nuevas_muertes = [m for m in nuevas_muertes if m["hf_id"] in vivos_antes]
    nuevas_muertes.sort(key=lambda m: m["death_year"] or 0, reverse=True)

    # Artefactos de mi fortaleza sobre los que alguien ha formado una reclamacion.
    mis_artefactos = set()
    if site_id is not None:
        mis_artefactos = {
            r[0] for r in conn.execute(
                "SELECT artifact_id FROM artifacts WHERE export_id = ? AND site_id = ?",
                (export_hasta, site_id),
            )
        }
    reclamaciones = [
        e for e in nuevos_eventos
        if _tipo_en(e["tipo"], RECLAMACION)
        and (e["artifact_id"] in mis_artefactos or e["en_mi_fortaleza"])
    ]

    return {
        "eventos_nuevos": len(nuevos_eventos),
        "en_mi_fortaleza": [e for e in nuevos_eventos if e["en_mi_fortaleza"]],
        "ataques_cerca": [
            e for e in nuevos_eventos
            if _tipo_en(e["tipo"], ATAQUE) and (e["cerca"] or e["en_mi_fortaleza"])
        ],
        "llegadas": [e for e in nuevos_eventos if _tipo_en(e["tipo"], LLEGADA) and (e["cerca"] or e["en_mi_fortaleza"])],
        "caravanas": [e for e in nuevos_eventos if _tipo_en(e["tipo"], COMERCIO) and (e["cerca"] or e["en_mi_fortaleza"])],
        "reclamaciones": reclamaciones,
        "artefactos_nuevos": nuevos_artefactos,
        "muertes_nuevas": nuevas_muertes[:200],
        "sitios_nuevos": nuevos_sitios,
        "otros_eventos": [
            e for e in nuevos_eventos
            if not e["en_mi_fortaleza"] and not e["cerca"]
        ][:300],
    }


# ------------------------------------------------------------------ avisos
def alerts(
    conn: sqlite3.Connection, export_id: int, site_id: int, radio: int = 20
) -> dict:
    sitio = dbmod.one(
        conn,
        "SELECT coord_x, coord_y, root_civ_id, owner_id FROM sites WHERE export_id = ? AND site_id = ?",
        (export_id, site_id),
    )
    if sitio is None or sitio["coord_x"] is None:
        return {"radio": radio, "sitios_hostiles": [], "bestias": [], "guerras": []}

    fx, fy = sitio["coord_x"], sitio["coord_y"]
    mi_civ = sitio["root_civ_id"]

    guerras = dbmod.all_(
        conn,
        """SELECT c.collection_id, c.name, c.start_year, c.end_year,
                  c.attacking_enid, c.defending_enid,
                  a.name AS atacante, d.name AS defensor
             FROM event_collections c
             LEFT JOIN entities a ON a.export_id = c.export_id AND a.entity_id = c.attacking_enid
             LEFT JOIN entities d ON d.export_id = c.export_id AND d.entity_id = c.defending_enid
            WHERE c.export_id = ? AND LOWER(COALESCE(c.type,'')) = 'war'
              AND (c.attacking_enid = ? OR c.defending_enid = ?)
            ORDER BY c.start_year DESC""",
        (export_id, mi_civ, mi_civ),
    )
    activas = [g for g in guerras if g["end_year"] in (None, -1)]
    enemigos = set()
    for guerra in activas:
        for lado in (guerra["attacking_enid"], guerra["defending_enid"]):
            if lado is not None and lado != mi_civ:
                enemigos.add(lado)

    hostiles = []
    for row in conn.execute(
        """SELECT site_id, name, type, coord_x, coord_y, owner_id, root_civ_id, state
             FROM sites WHERE export_id = ? AND coord_x IS NOT NULL""",
        (export_id,),
    ):
        if row["site_id"] == site_id or row["state"] == L.STATE_RUINS:
            continue
        dist = max(abs(row["coord_x"] - fx), abs(row["coord_y"] - fy))
        if dist > radio:
            continue
        civ = row["root_civ_id"]
        if civ is not None and civ == mi_civ:
            continue
        en_guerra = civ in enemigos
        if civ is None and L.site_layer(row["type"]) == "asentamiento":
            continue
        hostiles.append(
            {
                "site_id": row["site_id"],
                "nombre": row["name"],
                "tipo": row["type"],
                "capa": L.site_layer(row["type"]),
                "distancia": dist,
                "civ_id": civ,
                "en_guerra": en_guerra,
                "motivo": "guerra activa" if en_guerra else (
                    "civilizacion ajena" if civ is not None else "sitio sin duenyo conocido"
                ),
            }
        )
    hostiles.sort(key=lambda h: (not h["en_guerra"], h["distancia"]))

    tipos = tuple(sorted(L.BEAST_TYPES))
    marcas = ",".join("?" * len(tipos))
    bestias = []
    for row in conn.execute(
        f"""SELECT h.hf_id, h.name, h.race, h.associated_type, s.site_id, s.name AS sitio,
                   s.coord_x, s.coord_y
              FROM historical_figures h
              JOIN hf_site_links l ON l.export_id = h.export_id AND l.hf_id = h.hf_id
              JOIN sites s ON s.export_id = h.export_id AND s.site_id = l.site_id
             WHERE h.export_id = ? AND h.alive = 1
               AND LOWER(COALESCE(h.associated_type,'')) IN ({marcas})
               AND s.coord_x IS NOT NULL""",
        (export_id, *tipos),
    ):
        dist = max(abs(row["coord_x"] - fx), abs(row["coord_y"] - fy))
        if dist <= radio:
            bestias.append(
                {
                    "hf_id": row["hf_id"],
                    "nombre": row["name"],
                    "raza": row["race"],
                    "tipo": row["associated_type"],
                    "sitio": row["sitio"],
                    "site_id": row["site_id"],
                    "distancia": dist,
                }
            )
    bestias.sort(key=lambda b: b["distancia"])
    vistas = set()
    unicas = []
    for bestia in bestias:
        if bestia["hf_id"] in vistas:
            continue
        vistas.add(bestia["hf_id"])
        unicas.append(bestia)

    return {
        "radio": radio,
        "sitios_hostiles": hostiles[:60],
        "bestias": unicas[:60],
        "guerras": activas,
        "guerras_pasadas": [g for g in guerras if g not in activas][:20],
    }
