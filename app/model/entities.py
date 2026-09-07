"""Jerarquia de entidades.

En el XML las entidades se anidan mediante elementos <child>: un gobierno de
sitio (type=sitegovernment) es hijo de una civilizacion (type=civilization).
Para saber a que civilizacion pertenece un sitio hay que subir por esa cadena
hasta la raiz. Aqui se calcula una vez y se guarda en columnas.
"""

from __future__ import annotations

import sqlite3


def rebuild_hierarchy(conn: sqlite3.Connection, export_id: int) -> None:
    padres: dict[int, int] = {}
    for row in conn.execute(
        "SELECT parent_id, child_id FROM entity_children WHERE export_id = ?", (export_id,)
    ):
        # Si un hijo apareciese con dos padres, gana el primero: la cadena real
        # de DF es un arbol.
        padres.setdefault(row["child_id"], row["parent_id"])

    ids = [r["entity_id"] for r in conn.execute(
        "SELECT entity_id FROM entities WHERE export_id = ?", (export_id,)
    )]

    filas = []
    for eid in ids:
        actual = eid
        depth = 0
        visto = {eid}
        while True:
            padre = padres.get(actual)
            if padre is None or padre in visto:
                break
            visto.add(padre)
            actual = padre
            depth += 1
            if depth > 64:  # guarda contra ciclos raros
                break
        filas.append((padres.get(eid), actual, depth, export_id, eid))

    conn.executemany(
        "UPDATE entities SET parent_id = ?, root_id = ?, depth = ? WHERE export_id = ? AND entity_id = ?",
        filas,
    )
