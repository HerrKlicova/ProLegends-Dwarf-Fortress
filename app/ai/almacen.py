"""Guardado de las crónicas en ficheros, no en la base de datos.

Las crónicas son lo único de esta aplicación que **cuesta dinero** y que no se
puede volver a obtener gratis: todo lo demás se reconstruye reimportando los
XML en unos minutos. Por eso no viven en la base de datos, que se borra y se
regenera con soltura, sino en ficheros de texto propios:

    data/cronicas/<mundo>/figura-1234.md
    data/cronicas/<mundo>/anyos-1-103.md
    data/cronicas/<mundo>/fortaleza-120.md

Así se pueden leer con el Bloc de notas sin abrir el programa, copiar a otro
ordenador arrastrando una carpeta, y sobre todo: no se pierden al borrar la
base de datos ni al descargarse una versión nueva.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import config
from ..parser.organizer import slug

SEPARADOR = "---"
CAMPOS = ("mundo", "ambito", "clave", "titulo", "modelo", "generada",
          "tokens_entrada", "tokens_salida", "export_id")

# Cómo se llama cada ámbito de cara al usuario.
NOMBRES_AMBITO = {
    "anyos": "Rangos de años",
    "figura": "Figuras históricas",
    "fortaleza": "Lugares y fortalezas",
}
ORDEN_AMBITO = ("anyos", "figura", "fortaleza")


def carpeta_base() -> Path:
    return config.DATA_DIR / "cronicas"


def carpeta_mundo(mundo: str) -> Path:
    return carpeta_base() / slug(mundo, "mundo")


def _nombre_fichero(ambito: str, clave: str) -> str:
    # 'figura:1234' -> 'figura-1234.md'
    limpia = clave.replace(":", "-")
    limpia = re.sub(r"[^A-Za-z0-9._-]+", "-", limpia).strip("-")
    return f"{limpia or ambito}.md"


def ruta(mundo: str, ambito: str, clave: str) -> Path:
    return carpeta_mundo(mundo) / _nombre_fichero(ambito, clave)


# ------------------------------------------------------------------ escribir
def guardar(mundo: str, ambito: str, clave: str, datos: dict) -> Path:
    destino = ruta(mundo, ambito, clave)
    destino.parent.mkdir(parents=True, exist_ok=True)

    cabecera = {
        "mundo": mundo,
        "ambito": ambito,
        "clave": clave,
        "titulo": datos.get("titulo") or "",
        "modelo": datos.get("modelo") or "",
        "generada": datos.get("creada") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tokens_entrada": datos.get("tokens_entrada"),
        "tokens_salida": datos.get("tokens_salida"),
        "export_id": datos.get("export_id"),
    }
    lineas = [SEPARADOR]
    for campo in CAMPOS:
        valor = cabecera.get(campo)
        if valor not in (None, ""):
            lineas.append(f"{campo}: {str(valor).replace(chr(10), ' ')}")
    lineas.append(SEPARADOR)
    lineas.append("")
    lineas.append(datos.get("texto") or "")

    # Se escribe primero en un fichero temporal: si algo falla a mitad, la
    # crónica anterior sigue intacta.
    temporal = destino.with_suffix(".md.tmp")
    temporal.write_text("\n".join(lineas), encoding="utf-8")
    temporal.replace(destino)
    return destino


# --------------------------------------------------------------------- leer
def _parsear(texto: str) -> dict:
    cabecera: dict = {}
    cuerpo = texto
    if texto.startswith(SEPARADOR):
        partes = texto.split(SEPARADOR, 2)
        if len(partes) == 3:
            for linea in partes[1].strip().splitlines():
                if ":" in linea:
                    clave, _, valor = linea.partition(":")
                    cabecera[clave.strip()] = valor.strip()
            cuerpo = partes[2].lstrip("\n")
    for numerico in ("tokens_entrada", "tokens_salida", "export_id"):
        if numerico in cabecera:
            try:
                cabecera[numerico] = int(cabecera[numerico])
            except ValueError:
                cabecera.pop(numerico)
    cabecera["texto"] = cuerpo.rstrip() + "\n" if cuerpo.strip() else ""
    return cabecera


def leer(mundo: str, ambito: str, clave: str) -> Optional[dict]:
    fichero = ruta(mundo, ambito, clave)
    if not fichero.exists():
        return None
    try:
        datos = _parsear(fichero.read_text(encoding="utf-8"))
    except OSError:
        return None
    if not datos.get("texto"):
        return None
    datos.setdefault("mundo", mundo)
    datos.setdefault("ambito", ambito)
    datos.setdefault("clave", clave)
    datos["fichero"] = str(fichero)
    return datos


def listar(mundo: Optional[str] = None) -> list[dict]:
    """Todas las crónicas guardadas, agrupables por ámbito."""
    carpetas = [carpeta_mundo(mundo)] if mundo else []
    if not carpetas and carpeta_base().exists():
        carpetas = [c for c in carpeta_base().iterdir() if c.is_dir()]

    salida: list[dict] = []
    for carpeta in carpetas:
        if not carpeta.exists():
            continue
        for fichero in sorted(carpeta.glob("*.md")):
            try:
                datos = _parsear(fichero.read_text(encoding="utf-8"))
            except OSError:
                continue
            if not datos.get("texto"):
                continue
            datos["fichero"] = str(fichero)
            datos["palabras"] = len(datos["texto"].split())
            datos.pop("texto", None)   # el listado no necesita el texto entero
            salida.append(datos)
    salida.sort(key=lambda c: (c.get("generada") or ""), reverse=True)
    return salida


def borrar(mundo: str, ambito: str, clave: str) -> bool:
    fichero = ruta(mundo, ambito, clave)
    try:
        fichero.unlink()
        return True
    except OSError:
        return False


# ---------------------------------------------------- traer las antiguas
def migrar_desde_bd(conn) -> int:
    """Saca a fichero las crónicas que quedasen guardadas en la base de datos.

    Las versiones anteriores a la 1.2.0 las guardaban ahí dentro. Esto se
    ejecuta al arrancar para que nadie pierda lo que ya había pagado.
    """
    try:
        filas = conn.execute(
            """SELECT c.scope_type, c.scope_key, c.title, c.text, c.model,
                      c.created_at, c.tokens_in, c.tokens_out, c.export_id,
                      w.name AS mundo
                 FROM chronicles c JOIN worlds w ON w.id = c.world_id"""
        ).fetchall()
    except Exception:
        return 0

    migradas = 0
    for fila in filas:
        if not fila["text"] or not fila["mundo"]:
            continue
        if leer(fila["mundo"], fila["scope_type"], fila["scope_key"]):
            continue          # ya está en disco, no se toca
        guardar(
            fila["mundo"], fila["scope_type"], fila["scope_key"],
            {
                "titulo": fila["title"],
                "texto": fila["text"],
                "modelo": fila["model"],
                "creada": fila["created_at"],
                "tokens_entrada": fila["tokens_in"],
                "tokens_salida": fila["tokens_out"],
                "export_id": fila["export_id"],
            },
        )
        migradas += 1
    return migradas
