"""Utilidades compartidas por los endpoints."""

from __future__ import annotations

import colorsys
import hashlib
import json
import sqlite3
from typing import Any, Optional

from fastapi import Depends

from .. import db as dbmod
from ..errors import NotFoundError


def get_conn():
    conn = dbmod.connect()
    try:
        dbmod.init_db(conn)
        yield conn
    finally:
        conn.close()


Conn = Depends(get_conn)


# Paleta por export, calculada una vez y reutilizada.
_PALETAS: dict[int, dict[str, str]] = {}


def _hsl(tono: float, saturacion: float, luz: float) -> str:
    r, g, b = colorsys.hls_to_rgb(tono % 1.0, luz, saturacion)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def spread_palette(claves) -> dict[str, str]:
    """Reparte los tonos del circulo cromatico entre las claves que haya.

    Los colores salen de los propios datos (la lista de razas del mundo), no de
    ninguna tabla fija, pero quedan bien separados entre si en lugar de caer al
    azar en la misma zona del espectro.
    """
    ordenadas = sorted({c for c in claves if c})
    total = len(ordenadas) or 1
    salida: dict[str, str] = {}
    for i, clave in enumerate(ordenadas):
        digest = hashlib.md5(clave.encode("utf-8")).digest()
        tono = (i / total) + 0.045  # desplazamiento para evitar el rojo puro
        saturacion = 0.50 + (digest[0] / 255.0) * 0.26
        luz = 0.50 + (digest[1] / 255.0) * 0.14
        salida[clave] = _hsl(tono, saturacion, luz)
    return salida


def race_bands(conn: sqlite3.Connection, export_id: int) -> dict[str, tuple[float, float]]:
    """Franja del circulo cromatico que le toca a cada raza: (centro, ancho)."""
    razas = sorted(race_palette(conn, export_id).keys())
    total = len(razas) or 1
    ancho = 1.0 / total
    return {raza: ((i + 0.5) * ancho + 0.045, ancho) for i, raza in enumerate(razas)}


def race_palette(conn: sqlite3.Connection, export_id: int) -> dict[str, str]:
    if export_id in _PALETAS:
        return _PALETAS[export_id]
    razas = [
        r[0] for r in conn.execute(
            """SELECT DISTINCT race FROM entities
                WHERE export_id = ? AND race IS NOT NULL AND race <> ''""",
            (export_id,),
        )
    ]
    razas += [
        r[0] for r in conn.execute(
            """SELECT DISTINCT race FROM historical_figures
                WHERE export_id = ? AND race IS NOT NULL AND race <> ''""",
            (export_id,),
        )
    ]
    paleta = spread_palette(razas)
    _PALETAS[export_id] = paleta
    return paleta


def color_de(conn: sqlite3.Connection, export_id: int, raza, alternativa="") -> str:
    """Color de una raza; si no hay raza, uno estable derivado del nombre."""
    if raza:
        paleta = race_palette(conn, export_id)
        if raza in paleta:
            return paleta[raza]
    return color_for(raza or alternativa)


def color_for(clave: str) -> str:
    """Color estable deducido del propio dato (nombre de raza o de faccion).

    No hay ninguna paleta fija por mundo: el mismo texto da siempre el mismo
    color, y textos distintos dan colores bien separados.
    """
    if not clave:
        return "#8a8f98"
    digest = hashlib.md5(clave.encode("utf-8")).digest()
    tono = digest[0] / 255.0
    saturacion = 0.45 + (digest[1] / 255.0) * 0.35
    luz = 0.48 + (digest[2] / 255.0) * 0.18
    r, g, b = colorsys.hls_to_rgb(tono, luz, saturacion)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def load_json(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def get_export(conn: sqlite3.Connection, export_id: int) -> dict:
    row = dbmod.one(conn, "SELECT * FROM exports WHERE id = ?", (export_id,))
    if row is None:
        raise NotFoundError(f"No existe el export número {export_id}.")
    if row["status"] != "ok":
        raise NotFoundError(
            f"El export '{row['prefix']}' no se importo correctamente.",
            row["message"] or "",
        )
    return row


def get_world(conn: sqlite3.Connection, world_id: int) -> dict:
    row = dbmod.one(conn, "SELECT * FROM worlds WHERE id = ?", (world_id,))
    if row is None:
        raise NotFoundError(f"No existe el mundo número {world_id}.")
    return row


def world_exports(conn: sqlite3.Connection, world_id: int) -> list[dict]:
    """Exports correctos de un mundo, del más antiguo al más reciente."""
    return dbmod.all_(
        conn,
        """SELECT * FROM exports WHERE world_id = ? AND status = 'ok'
            ORDER BY COALESCE(game_year, 0), COALESCE(game_month, 0),
                     COALESCE(game_day, 0), id""",
        (world_id,),
    )


def latest_export(conn: sqlite3.Connection, world_id: int) -> dict:
    exports = world_exports(conn, world_id)
    if not exports:
        raise NotFoundError("Ese mundo no tiene ningún export importado correctamente.")
    return exports[-1]


def entity_index(conn: sqlite3.Connection, export_id: int) -> dict[int, dict]:
    """Todas las entidades del export indexadas por id, con su color.

    Cada raza ocupa una franja del circulo cromatico, y las civilizaciones de
    una misma raza se reparten dentro de su franja: asi dos civilizaciones de
    goblins se parecen entre si pero no se confunden la una con la otra.
    """
    filas = dbmod.all_(
        conn,
        """SELECT entity_id, name, type, race, parent_id, root_id, depth
             FROM entities WHERE export_id = ?""",
        (export_id,),
    )
    salida: dict[int, dict] = {r["entity_id"]: r for r in filas}

    bandas = race_bands(conn, export_id)
    raices = [r for r in filas if r["root_id"] == r["entity_id"]]
    por_raza: dict[str, list] = {}
    for raiz in sorted(raices, key=lambda r: r["entity_id"]):
        por_raza.setdefault(raiz["race"] or "", []).append(raiz)

    colores: dict[int, str] = {}
    for raza, lista in por_raza.items():
        centro, ancho = bandas.get(raza, (None, 0.0))
        for i, ent in enumerate(lista):
            if centro is None:
                colores[ent["entity_id"]] = color_for(ent["name"] or str(ent["entity_id"]))
                continue
            # Se reparten dentro de la franja de su raza. El tono apenas se
            # mueve (para no invadir la franja de la raza vecina); lo que de
            # verdad las separa es el brillo.
            desplazamiento = 0.0 if len(lista) == 1 else (
                (i / (len(lista) - 1) - 0.5) * ancho * 0.4
            )
            digest = hashlib.md5((ent["name"] or "").encode("utf-8")).digest()
            colores[ent["entity_id"]] = _hsl(
                centro + desplazamiento,
                0.48 + (digest[0] / 255.0) * 0.22,
                0.40 + (i % 4) * 0.09,
            )

    for fila in filas:
        raiz = colores.get(fila["root_id"])
        fila["color"] = raiz or color_de(
            conn, export_id, fila["race"], fila["name"] or str(fila["entity_id"])
        )
    return salida


def hf_names(conn: sqlite3.Connection, export_id: int, ids: list[int]) -> dict[int, str]:
    ids = [i for i in dict.fromkeys(ids) if i is not None]
    if not ids:
        return {}
    salida: dict[int, str] = {}
    for trozo in _chunks(ids, 400):
        marcas = ",".join("?" * len(trozo))
        for row in conn.execute(
            f"SELECT hf_id, name FROM historical_figures WHERE export_id = ? AND hf_id IN ({marcas})",
            (export_id, *trozo),
        ):
            salida[row["hf_id"]] = row["name"]
    return salida


def site_names(conn: sqlite3.Connection, export_id: int, ids: list[int]) -> dict[int, str]:
    ids = [i for i in dict.fromkeys(ids) if i is not None]
    if not ids:
        return {}
    salida: dict[int, str] = {}
    for trozo in _chunks(ids, 400):
        marcas = ",".join("?" * len(trozo))
        for row in conn.execute(
            f"SELECT site_id, name FROM sites WHERE export_id = ? AND site_id IN ({marcas})",
            (export_id, *trozo),
        ):
            salida[row["site_id"]] = row["name"]
    return salida


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def event_payload(row: dict, incluir_json: bool = True) -> dict:
    """Convierte una fila de evento en algo presentable, sin inventar campos."""
    datos = load_json(row.get("data_json")) if incluir_json else {}
    for clave in ("id", "type", "year", "seconds72"):
        datos.pop(clave, None)
    return {
        "id": row.get("event_id"),
        "anyo": row.get("year"),
        "tipo": row.get("type"),
        "site_id": row.get("site_id"),
        "hfid": row.get("hfid"),
        "slayer_hfid": row.get("slayer_hfid"),
        "civ_id": row.get("civ_id"),
        "attacker_civ_id": row.get("attacker_civ_id"),
        "defender_civ_id": row.get("defender_civ_id"),
        "artifact_id": row.get("artifact_id"),
        "detalles": {k: v for k, v in datos.items() if v not in (None, "", [], {})},
    }


def narrar(conn: sqlite3.Connection, export_id: int,
           filas: list[dict], eventos: list[dict]) -> list[dict]:
    """Añade a cada evento su frase en castellano.

    Se hace en una tanda: el narrador resuelve de golpe todos los nombres que
    hagan falta en vez de preguntar por cada evento.
    """
    from ..model.narrador import Narrador

    narrador = Narrador(conn, export_id)
    narrador.preparar(filas)
    for fila, evento in zip(filas, eventos):
        evento["frase"] = narrador.frase(fila)
    return eventos
