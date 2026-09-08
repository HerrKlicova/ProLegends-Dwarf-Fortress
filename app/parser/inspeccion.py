"""Mirar qué trae de verdad un export, sin suponer nada.

Existe porque suponer sale caro: se dio por hecho que las casillas de un río
venían en el orden en que se recorre, y no era así. Cuando algo del mapa no
cuadra con lo que enseña el juego, esto saca una muestra pequeña del XML —
unos pocos registros tal cual vienen— que se puede leer de un vistazo o pegar
en una conversación sin mover ficheros de 45 MB.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional

from .xmlstream import iter_sections

# Las secciones que describen la geografía del mundo.
SECCIONES_MAPA = ("rivers", "world_constructions", "mountain_peaks", "regions",
                  "underground_regions", "landmasses")

MUESTRAS = 3
RECORTE = 900   # caracteres por registro: basta para ver la forma


def _texto(elem: ET.Element) -> str:
    try:
        crudo = ET.tostring(elem, encoding="unicode")
    except Exception:  # pragma: no cover
        return "<no se ha podido volcar este registro>"
    crudo = " ".join(crudo.split())
    if len(crudo) > RECORTE:
        crudo = crudo[:RECORTE] + f"  ... [recortado, ocupaba {len(crudo)} caracteres]"
    return crudo


def inspeccionar(path: Path, secciones: Iterable[str] = SECCIONES_MAPA,
                 muestras: int = MUESTRAS) -> dict:
    """Cuenta los registros de cada sección y guarda unos pocos enteros."""
    secciones = set(secciones)
    cuenta: dict[str, int] = {}
    ejemplos: dict[str, list[str]] = {}
    campos: dict[str, dict[str, int]] = {}

    for seccion, elem, _ in iter_sections(Path(path)):
        if elem is None or seccion not in secciones:
            continue
        cuenta[seccion] = cuenta.get(seccion, 0) + 1
        vistos = campos.setdefault(seccion, {})
        for hijo in elem:
            vistos[hijo.tag] = vistos.get(hijo.tag, 0) + 1
        lista = ejemplos.setdefault(seccion, [])
        if len(lista) < muestras:
            lista.append(_texto(elem))
    return {"fichero": str(path), "cuenta": cuenta, "ejemplos": ejemplos,
            "campos": campos}


def informe(rutas: Iterable[Path], salida: Optional[Path] = None) -> str:
    """Informe legible de lo que traen esos ficheros."""
    lineas: list[str] = []
    lineas.append("INFORME DE GEOGRAFÍA DE PROLEGENDS")
    lineas.append("Muestra de lo que traen los XML, para poder dibujar el mapa")
    lineas.append("con lo que hay de verdad y no con lo que uno se imagina.")
    lineas.append("")

    for ruta in rutas:
        datos = inspeccionar(Path(ruta))
        lineas.append("=" * 70)
        lineas.append(f"FICHERO: {Path(ruta).name}")
        tam = Path(ruta).stat().st_size / 1048576
        lineas.append(f"  ocupa {tam:.1f} MB")
        lineas.append("")
        if not datos["cuenta"]:
            lineas.append("  (este fichero no trae ninguna sección de geografía)")
            lineas.append("")
            continue
        for seccion, n in sorted(datos["cuenta"].items()):
            lineas.append(f"  --- {seccion}: {n} registros ---")
            usados = datos["campos"].get(seccion, {})
            if usados:
                detalle = ", ".join(
                    f"{k} (en {v} de {n})" for k, v in sorted(usados.items(),
                                                             key=lambda kv: -kv[1])
                )
                lineas.append(f"      campos que aparecen: {detalle}")
            for i, ejemplo in enumerate(datos["ejemplos"].get(seccion, []), 1):
                lineas.append(f"      ejemplo {i}: {ejemplo}")
            lineas.append("")

    texto = "\n".join(lineas)
    if salida is not None:
        Path(salida).write_text(texto, encoding="utf-8")
    return texto


# --------------------------------------------------------------- desde la BD
def informe_bd(conn, export_id: int, muestras: int = MUESTRAS) -> str:
    """El mismo informe, pero sacado de la base de datos.

    Sirve cuando los XML ya no están a mano (se importaron y luego se movieron,
    o se está mirando desde otro ordenador). Se ve el registro tal y como quedó
    guardado en vez del XML crudo, que para averiguar qué campos trae cada cosa
    es igual de útil.
    """
    import json
    import sqlite3  # noqa: F401  (solo para el tipo)

    lineas: list[str] = []
    lineas.append("INFORME DE GEOGRAFÍA DE PROLEGENDS")
    lineas.append("Sacado de la base de datos (los XML no estaban a mano).")
    lineas.append("Muestra de lo que trae este export sobre el mapa.")
    lineas.append("")

    fila = conn.execute(
        "SELECT prefix, world_width, world_height FROM exports WHERE id = ?",
        (export_id,),
    ).fetchone()
    if fila is not None:
        lineas.append(f"EXPORT: {fila['prefix']}   "
                      f"mundo de {fila['world_width']}x{fila['world_height']} casillas")
        lineas.append("")

    # Las regiones tienen tabla propia.
    total = conn.execute(
        "SELECT COUNT(*) FROM regions WHERE export_id = ? AND underground = 0",
        (export_id,),
    ).fetchone()[0]
    lineas.append(f"  --- regions: {total} registros ---")
    for r in conn.execute(
        """SELECT region_id, name, type, data_json FROM regions
            WHERE export_id = ? AND underground = 0 ORDER BY region_id LIMIT ?""",
        (export_id, muestras),
    ):
        try:
            datos = json.loads(r["data_json"] or "{}")
        except (ValueError, TypeError):
            datos = {}
        claves = ", ".join(sorted(datos)) if isinstance(datos, dict) else "?"
        lineas.append(f"      region {r['region_id']}  nombre={r['name']!r}  "
                      f"tipo={r['type']!r}")
        lineas.append(f"        campos: {claves}")
        if isinstance(datos, dict):
            for clave, valor in sorted(datos.items()):
                texto = str(valor)
                if len(texto) > 220:
                    texto = texto[:220] + f"  ... [recortado, ocupaba {len(texto)}]"
                lineas.append(f"        {clave}: {texto}")
    lineas.append("")

    # Lo demás cae en el cajón de sastre.
    secciones = [f["section"] for f in conn.execute(
        """SELECT section, COUNT(*) n FROM raw_records WHERE export_id = ?
            GROUP BY section ORDER BY section""", (export_id,))]
    for seccion in secciones:
        n = conn.execute(
            "SELECT COUNT(*) FROM raw_records WHERE export_id = ? AND section = ?",
            (export_id, seccion),
        ).fetchone()[0]
        interesa = any(p in seccion for p in
                       ("river", "construction", "peak", "region", "landmass"))
        lineas.append(f"  --- {seccion}: {n} registros ---"
                      + ("" if interesa else "   (no es geografía; solo el recuento)"))
        if not interesa:
            continue
        campos: dict[str, int] = {}
        for f in conn.execute(
            "SELECT data_json FROM raw_records WHERE export_id = ? AND section = ?",
            (export_id, seccion),
        ):
            try:
                d = json.loads(f["data_json"] or "{}")
            except (ValueError, TypeError):
                continue
            if isinstance(d, dict):
                for k in d:
                    campos[k] = campos.get(k, 0) + 1
        if campos:
            lineas.append("      campos que aparecen: " + ", ".join(
                f"{k} (en {v} de {n})" for k, v in sorted(campos.items(),
                                                          key=lambda kv: -kv[1])))
        for i, f in enumerate(conn.execute(
            """SELECT data_json FROM raw_records WHERE export_id = ? AND section = ?
                LIMIT ?""", (export_id, seccion, muestras)), 1):
            try:
                d = json.loads(f["data_json"] or "{}")
            except (ValueError, TypeError):
                continue
            lineas.append(f"      ejemplo {i}:")
            if isinstance(d, dict):
                for clave, valor in sorted(d.items()):
                    texto = str(valor)
                    if len(texto) > RECORTE:
                        texto = texto[:RECORTE] + f"  ... [recortado, ocupaba {len(texto)}]"
                    lineas.append(f"        {clave}: {texto}")
        lineas.append("")

    return "\n".join(lineas)
