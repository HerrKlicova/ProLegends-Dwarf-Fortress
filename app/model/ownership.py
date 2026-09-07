"""Reconstruccion cronologica de la propiedad de los sitios.

El XML no trae un campo "quién manda aquí". Hay que deducirlo recorriendo los
eventos historicos ordenados por año:

    'created site'                        -> el propietario pasa a ser civ_id
    'site taken over'                     -> el propietario pasa a ser attacker_civ_id
    'destroyed site' / 'hf destroyed site' -> el sitio queda en ruinas

Se guarda el HISTORICO COMPLETO (una fila por cambio), no solo el estado final,
porque es lo que alimenta el deslizador de año del mapa.
"""

from __future__ import annotations

import sqlite3

from ..parser import legends as L


def rebuild_ownership(conn: sqlite3.Connection, export_id: int) -> None:
    conn.execute("DELETE FROM site_ownership WHERE export_id = ?", (export_id,))

    tipos = tuple(sorted(L.OWNERSHIP_TYPES))
    placeholders = ",".join("?" * len(tipos))
    filas = []
    con_evento: set[int] = set()

    for row in conn.execute(
        f"""SELECT event_id, year, seconds72, type, site_id, civ_id, site_civ_id,
                   attacker_civ_id, data_json
              FROM events
             WHERE export_id = ? AND type IN ({placeholders}) AND site_id IS NOT NULL
             ORDER BY year, seconds72, event_id""",
        (export_id, *tipos),
    ):
        import json

        record = json.loads(row["data_json"]) if row["data_json"] else {}
        cambio = L.ownership_change(record, row["type"] or "")
        if cambio is None:
            continue
        owner, state = cambio
        con_evento.add(row["site_id"])
        filas.append(
            (export_id, row["site_id"], row["year"] if row["year"] is not None else 0,
             row["seconds72"] or 0, owner, state, row["event_id"], row["type"], "evento")
        )

    # Sitios que nunca aparecen en un evento de creacion pero que el _plus dice
    # que pertenecen a alguien (guaridas, fortalezas oscuras antiguas...). Se
    # anota una fila inicial en el primer año conocido del mundo.
    primer_anyo = conn.execute(
        "SELECT COALESCE(MIN(year), 0) FROM events WHERE export_id = ? AND year >= 0",
        (export_id,),
    ).fetchone()[0]

    for row in conn.execute(
        "SELECT site_id, civ_id, cur_owner_id FROM sites WHERE export_id = ?", (export_id,)
    ):
        if row["site_id"] in con_evento:
            continue
        owner = row["cur_owner_id"] if row["cur_owner_id"] is not None else row["civ_id"]
        if owner is None:
            continue
        filas.append(
            (export_id, row["site_id"], primer_anyo, 0, owner, L.STATE_ACTIVE, None, None, "inicial")
        )

    conn.executemany(
        """INSERT INTO site_ownership
           (export_id, site_id, year, seconds72, owner_entity_id, state, event_id, event_type, source)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        filas,
    )

    _apply_current_state(conn, export_id)


def _apply_current_state(conn: sqlite3.Connection, export_id: int) -> None:
    """Vuelca en la tabla sites el último estado conocido y el año de fundacion."""
    conn.execute(
        """UPDATE sites SET
             owner_id = (
                SELECT o.owner_entity_id FROM site_ownership o
                 WHERE o.export_id = sites.export_id AND o.site_id = sites.site_id
                 ORDER BY o.year DESC, o.seconds72 DESC, o.rowid DESC LIMIT 1),
             state = COALESCE((
                SELECT o.state FROM site_ownership o
                 WHERE o.export_id = sites.export_id AND o.site_id = sites.site_id
                 ORDER BY o.year DESC, o.seconds72 DESC, o.rowid DESC LIMIT 1), ?),
             founded_year = (
                SELECT MIN(o.year) FROM site_ownership o
                 WHERE o.export_id = sites.export_id AND o.site_id = sites.site_id
                   AND o.source = 'evento')
           WHERE export_id = ?""",
        (L.STATE_UNKNOWN, export_id),
    )
    # Si el _plus dice quien es el propietario actual y la cronologia no lo sabe,
    # se usa el dato del XML.
    conn.execute(
        """UPDATE sites SET owner_id = COALESCE(cur_owner_id, civ_id)
            WHERE export_id = ? AND owner_id IS NULL AND state <> ?""",
        (export_id, L.STATE_RUINS),
    )
    # Civilizacion raíz del propietario, subiendo por la jerarquía de entidades.
    conn.execute(
        """UPDATE sites SET root_civ_id = (
                SELECT e.root_id FROM entities e
                 WHERE e.export_id = sites.export_id AND e.entity_id = sites.owner_id)
            WHERE export_id = ?""",
        (export_id,),
    )


def owner_at_year(conn: sqlite3.Connection, export_id: int, year: int) -> dict[int, dict]:
    """Estado de todos los sitios en un anyo dado: {site_id: {owner, state}}."""
    estado: dict[int, dict] = {}
    for row in conn.execute(
        """SELECT site_id, owner_entity_id, state FROM site_ownership
            WHERE export_id = ? AND year <= ?
            ORDER BY year, seconds72, rowid""",
        (export_id, year),
    ):
        estado[row["site_id"]] = {
            "owner_id": row["owner_entity_id"],
            "state": row["state"],
        }
    return estado
