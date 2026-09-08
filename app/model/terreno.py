"""El terreno del mundo, deducido de los datos que ya están importados.

Dwarf Fortress no da un mapa. Lo que da es, en el `_plus`, la lista de casillas
que ocupa cada región, y en el principal, cómo se llama esa región y de qué tipo
es (Ocean, Mountains, Forest...). Cruzando las dos cosas sale una rejilla de
biomas que cubre el mundo entero, y de ahí se puede dibujar un mapa de verdad:
la costa es exacta porque las regiones no dejan huecos.

Aquí no se inventa nada. Si un dato no está en el XML, no sale en el mapa: sin
coordenadas de región no hay costa, y se dice, en lugar de pintar una inventada.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterable, Optional

from .. import db as dbmod

# Un carácter por casilla: así la rejilla entera de un mundo grande viaja en un
# solo texto en vez de en 66.000 números.
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
SIN_DATO = "."

_PAR = re.compile(r"(-?\d+)\s*,\s*(-?\d+)")


def parse_coords(valor) -> list[tuple[int, int]]:
    """Saca pares x,y de como sea que vengan.

    DFHack los escribe como "x,y|x,y|x,y", pero según la versión pueden llegar
    separados por espacios o repartidos en varias etiquetas, así que se aceptan
    todas esas formas en lugar de dar por supuesta una.
    """
    if valor is None or valor is True:
        return []
    if isinstance(valor, (list, tuple)):
        salida: list[tuple[int, int]] = []
        for trozo in valor:
            salida.extend(parse_coords(trozo))
        return salida
    if isinstance(valor, dict):
        for clave in ("coords", "path", "points", "coord"):
            if clave in valor:
                return parse_coords(valor[clave])
        return []
    return [(int(m.group(1)), int(m.group(2))) for m in _PAR.finditer(str(valor))]


def _primer_coord(registro: dict) -> list[tuple[int, int]]:
    for clave in ("coords", "path", "points", "coord"):
        if clave in registro:
            pares = parse_coords(registro[clave])
            if pares:
                return pares
    return []


def _texto(valor) -> Optional[str]:
    if valor is None or valor is True:
        return None
    texto = str(valor).strip()
    return texto or None


def _entero(valor) -> Optional[int]:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _crudos(conn: sqlite3.Connection, export_id: int, secciones: Iterable[str]) -> list[dict]:
    """Registros del cajón de sastre, que es donde caen ríos y calzadas."""
    nombres = list(secciones)
    marcas = ",".join("?" * len(nombres))
    salida = []
    for fila in conn.execute(
        f"SELECT data_json FROM raw_records WHERE export_id = ? AND section IN ({marcas})",
        (export_id, *nombres),
    ):
        try:
            dato = json.loads(fila["data_json"] or "{}")
        except (ValueError, TypeError):
            continue
        if isinstance(dato, dict):
            salida.append(dato)
    return salida


def terreno(conn: sqlite3.Connection, export_id: int) -> dict:
    """Rejilla de biomas, ríos, calzadas y picos de un export."""
    regiones = dbmod.all_(
        conn,
        """SELECT region_id, name, type, data_json FROM regions
            WHERE export_id = ? AND underground = 0 ORDER BY region_id""",
        (export_id,),
    )

    catalogo: list[str] = []
    indice: dict[str, int] = {}
    celdas: dict[tuple[int, int], int] = {}
    ficha: list[dict] = []
    sin_coords = 0

    for region in regiones:
        try:
            datos = json.loads(region["data_json"] or "{}")
        except (ValueError, TypeError):
            datos = {}
        tipo = _texto(region["type"]) or _texto(datos.get("type")) or "Desconocido"
        if tipo not in indice:
            indice[tipo] = len(catalogo)
            catalogo.append(tipo)
        pares = _primer_coord(datos if isinstance(datos, dict) else {})
        ficha.append({"id": region["region_id"], "nombre": _texto(region["name"]),
                      "tipo": tipo, "casillas": len(pares)})
        if not pares:
            sin_coords += 1
            continue
        for x, y in pares:
            celdas[(x, y)] = indice[tipo]

    # El tamaño del mundo sale de los propios datos, nunca se supone.
    limites = _limites(conn, export_id, celdas)
    rejilla = _tejer(celdas, limites) if celdas else ""

    return {
        "hay_mapa": bool(celdas),
        "motivo": "" if celdas else (
            "Este export no trae las coordenadas de las regiones, así que no se "
            "puede dibujar la costa. Hace falta el fichero _legends_plus.xml que "
            "genera DFHack."
        ),
        **limites,
        "biomas": catalogo,
        "rejilla": rejilla,
        "regiones": ficha,
        "regiones_sin_coordenadas": sin_coords,
        "rios": _rios(conn, export_id),
        "construcciones": _construcciones(conn, export_id),
        "picos": _picos(conn, export_id),
    }


def _limites(conn: sqlite3.Connection, export_id: int, celdas: dict) -> dict:
    """Rectángulo que abarca el mundo, según regiones y sitios."""
    xs = [x for x, _ in celdas]
    ys = [y for _, y in celdas]
    fila = conn.execute(
        """SELECT MIN(coord_x), MIN(coord_y), MAX(coord_x), MAX(coord_y)
             FROM sites WHERE export_id = ? AND coord_x IS NOT NULL""",
        (export_id,),
    ).fetchone()
    if fila and fila[0] is not None:
        xs += [fila[0], fila[2]]
        ys += [fila[1], fila[3]]
    if not xs:
        return {"min_x": 0, "min_y": 0, "ancho": 0, "alto": 0}
    min_x, min_y = min(xs), min(ys)
    return {"min_x": min_x, "min_y": min_y,
            "ancho": max(xs) - min_x + 1, "alto": max(ys) - min_y + 1}


def _tejer(celdas: dict, limites: dict) -> str:
    """Una fila detrás de otra, un carácter por casilla."""
    ancho, alto = limites["ancho"], limites["alto"]
    min_x, min_y = limites["min_x"], limites["min_y"]
    filas = []
    for y in range(min_y, min_y + alto):
        fila = []
        for x in range(min_x, min_x + ancho):
            i = celdas.get((x, y))
            fila.append(SIN_DATO if i is None or i >= len(ALFABETO) else ALFABETO[i])
        filas.append("".join(fila))
    return "".join(filas)


def _rios(conn: sqlite3.Connection, export_id: int) -> list[dict]:
    salida = []
    for dato in _crudos(conn, export_id, ("rivers", "river")):
        camino = _primer_coord(dato)
        if len(camino) < 2:
            continue
        salida.append({"nombre": _texto(dato.get("name")), "camino": camino})
    salida.sort(key=lambda r: len(r["camino"]), reverse=True)
    return salida


def _construcciones(conn: sqlite3.Connection, export_id: int) -> list[dict]:
    salida = []
    for dato in _crudos(conn, export_id,
                        ("world_constructions", "world_construction")):
        camino = _primer_coord(dato)
        if len(camino) < 2:
            continue
        salida.append({
            "nombre": _texto(dato.get("name")),
            "tipo": (_texto(dato.get("type")) or "").lower() or None,
            "camino": camino,
        })
    return salida


def _picos(conn: sqlite3.Connection, export_id: int) -> list[dict]:
    salida = []
    for dato in _crudos(conn, export_id, ("mountain_peaks", "mountain_peak")):
        pares = _primer_coord(dato)
        if not pares:
            continue
        x, y = pares[0]
        salida.append({
            "nombre": _texto(dato.get("name")),
            "x": x, "y": y,
            "altura": _entero(dato.get("height")),
            "volcan": str(dato.get("is_volcano", "")).strip() in ("1", "true", "True"),
        })
    return salida


def extension(conn: sqlite3.Connection, export_id: int) -> Optional[tuple]:
    """Rectángulo que ocupan las regiones: (min_x, min_y, max_x, max_y).

    Solo mira las coordenadas, sin montar la rejilla, porque esto se usa para
    corregir el tamaño del mundo guardado y hay que poder hacerlo deprisa.
    """
    min_x = min_y = max_x = max_y = None
    for fila in conn.execute(
        "SELECT data_json FROM regions WHERE export_id = ? AND underground = 0",
        (export_id,),
    ):
        try:
            datos = json.loads(fila["data_json"] or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(datos, dict):
            continue
        for x, y in _primer_coord(datos):
            min_x = x if min_x is None or x < min_x else min_x
            max_x = x if max_x is None or x > max_x else max_x
            min_y = y if min_y is None or y < min_y else min_y
            max_y = y if max_y is None or y > max_y else max_y
    if min_x is None:
        return None
    return (min_x, min_y, max_x, max_y)


def ajustar_extension(conn: sqlite3.Connection, export_id: Optional[int] = None) -> int:
    """Corrige el tamaño del mundo guardado usando las regiones.

    Antes se deducía solo de dónde había sitios, y eso se queda corto: en un
    mundo hay mar y montañas donde no vive nadie. Las regiones sí cubren el
    mundo entero, así que mandan ellas. Se ejecuta al arrancar para que los
    exports importados con versiones anteriores queden bien sin reimportar.
    """
    if export_id is None:
        filas = dbmod.all_(conn, "SELECT id FROM exports WHERE status = 'ok'")
        ids = [f["id"] for f in filas]
    else:
        ids = [export_id]

    cambiados = 0
    for eid in ids:
        caja = extension(conn, eid)
        if caja is None:
            continue
        min_x, min_y, max_x, max_y = caja
        fila = dbmod.one(
            conn,
            """SELECT min_x, min_y, max_x, max_y, world_width, world_height
                 FROM exports WHERE id = ?""",
            (eid,),
        )
        if fila is None:
            continue
        for clave, valor, menor in (("min_x", min_x, True), ("min_y", min_y, True),
                                    ("max_x", max_x, False), ("max_y", max_y, False)):
            actual = fila[clave]
            if actual is not None:
                valor = min(actual, valor) if menor else max(actual, valor)
            if clave == "min_x":
                min_x = valor
            elif clave == "min_y":
                min_y = valor
            elif clave == "max_x":
                max_x = valor
            else:
                max_y = valor
        ancho, alto = max_x - min_x + 1, max_y - min_y + 1
        if (fila["world_width"], fila["world_height"]) == (ancho, alto):
            continue
        conn.execute(
            """UPDATE exports SET min_x = ?, min_y = ?, max_x = ?, max_y = ?,
                   world_width = ?, world_height = ? WHERE id = ?""",
            (min_x, min_y, max_x, max_y, ancho, alto, eid),
        )
        cambiados += 1
    return cambiados
