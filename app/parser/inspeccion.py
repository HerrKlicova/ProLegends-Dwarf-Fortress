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
