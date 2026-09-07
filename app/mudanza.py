"""Traslado de tus cosas a la carpeta personal.

Hasta la versión 1.3.0 todo vivía dentro de la carpeta del programa: las
crónicas, la clave de la API, la base de datos y los XML. Eso obligaba a
copiarlo a mano cada vez que bajabas una versión nueva, y bastaba con
despistarse una vez para perder crónicas que habían costado dinero.

Desde la 1.3.1 todo eso vive en tu carpeta personal (normalmente
`Documentos/ProLegends`), fuera del programa. Este módulo se encarga de la
mudanza, una sola vez, sin borrar nada que no sea recuperable.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Callable, Optional

from . import config


def _copiar_carpeta(origen: Path, destino: Path) -> int:
    """Copia lo que falte, sin pisar nada que ya esté en el destino."""
    copiados = 0
    for fichero in origen.rglob("*"):
        if not fichero.is_file():
            continue
        objetivo = destino / fichero.relative_to(origen)
        if objetivo.exists():
            continue
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fichero, objetivo)
        copiados += 1
    return copiados


def _mover_ficheros(origen: Path, destino: Path, patron: str) -> int:
    """Mueve ficheros grandes (en el mismo disco es instantáneo)."""
    movidos = 0
    for fichero in sorted(origen.rglob(patron)):
        if not fichero.is_file():
            continue
        objetivo = destino / fichero.relative_to(origen)
        if objetivo.exists():
            continue
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(fichero), str(objetivo))
        except OSError:
            continue
        movidos += 1
    return movidos


def _copiar_bd(origen: Path, destino: Path) -> bool:
    """Copia la base de datos dejándola consistente.

    No vale con copiar el fichero a secas: en modo WAL parte de lo escrito
    puede estar todavía en el fichero de al lado. Se usa la copia de seguridad
    que trae SQLite, que se ocupa de eso.
    """
    if destino.exists() or not origen.exists():
        return False
    try:
        entrada = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            salida = sqlite3.connect(destino)
            try:
                entrada.backup(salida)
            finally:
                salida.close()
        finally:
            entrada.close()
    except sqlite3.Error:
        destino.unlink(missing_ok=True)
        return False
    return True


# Nombres con los que suele quedarse la carpeta de una versión anterior:
# "ProLegends-Dwarf-Fortress-1.3.0", "ProLegends (1)", "prolegends-main"...
_PISTA_NOMBRE = "prolegends"


def _es_instalacion(carpeta: Path) -> bool:
    """¿Esa carpeta es una copia de ProLegends con datos tuyos dentro?"""
    try:
        if not carpeta.is_dir() or not (carpeta / "app").is_dir():
            return False
        datos = carpeta / "data"
        return ((datos / "cronicas").is_dir() or (datos / "db").is_dir()
                or (datos / "imports").is_dir() or (carpeta / ".env").exists())
    except OSError:
        return False


def instalaciones_anteriores() -> list[Path]:
    """Otras copias de ProLegends que haya por el ordenador, la más nueva primero.

    Hace falta porque lo normal es descomprimir cada versión en una carpeta
    nueva en vez de sobrescribir la anterior: las crónicas de la versión pasada
    están en OTRA carpeta, no en la del programa que se está ejecutando. Se
    mira solo donde tiene sentido —al lado de esta copia y en las carpetas de
    descargas, escritorio y documentos—, nunca el disco entero.
    """
    aqui = config.BASE_DIR.resolve()
    casa = Path.home()
    padres = [config.BASE_DIR.parent, casa]
    for nombre in ("Downloads", "Descargas", "Desktop", "Escritorio",
                   "Documents", "Documentos"):
        padres.append(casa / nombre)

    vistas: dict[str, Path] = {}
    for padre in padres:
        try:
            if not padre.is_dir():
                continue
            for hija in padre.iterdir():
                if _PISTA_NOMBRE not in hija.name.lower():
                    continue
                if hija.resolve() == aqui or not _es_instalacion(hija):
                    continue
                vistas[str(hija.resolve())] = hija
        except OSError:
            continue

    def cuando(carpeta: Path) -> float:
        try:
            return carpeta.stat().st_mtime
        except OSError:
            return 0.0

    # De la más reciente a la más antigua: si hay varias con crónicas se
    # rescatan todas, pero empezando por la que más al día está.
    return sorted(vistas.values(), key=cuando, reverse=True)[:6]


def migrar(log: Optional[Callable[[str], None]] = None) -> list[str]:
    """Trae a tu carpeta personal lo que quede en cualquier copia anterior."""
    log = log or (lambda mensaje: None)
    nueva = config.DATA_DIR
    hecho: list[str] = []
    if nueva.resolve() == config.DATA_DIR_ANTIGUA.resolve():
        return hecho

    config.ensure_dirs()
    # Primero esta misma carpeta, por si se actualizó encima; después las
    # copias anteriores que haya sueltas por el ordenador.
    for programa in [config.BASE_DIR, *instalaciones_anteriores()]:
        hecho += _rescatar(programa, nueva)

    if hecho:
        log("")
        log(f"  Tus cosas viven ahora en {nueva}")
        for linea in hecho:
            log(f"    - {linea}")
        log("  Esa carpeta ya no se toca al actualizar ProLegends.")
    return hecho


def _rescatar(programa: Path, nueva: Path) -> list[str]:
    """Copia a la carpeta personal lo que falte de una copia del programa."""
    antigua = programa / "data"
    hecho: list[str] = []
    if not antigua.is_dir() and not (programa / ".env").exists():
        return hecho
    donde = "" if programa.resolve() == config.BASE_DIR.resolve() else f" (de {programa.name})"

    # 1. Las crónicas: lo único que cuesta dinero y no se puede regenerar.
    #    Se copian, nunca se mueven: las de la carpeta vieja se quedan de
    #    respaldo por si acaso.
    viejas = antigua / "cronicas"
    if viejas.is_dir():
        cuantas = _copiar_carpeta(viejas, nueva / "cronicas")
        if cuantas:
            hecho.append(f"{cuantas} crónica(s) rescatadas{donde}")

    # 2. La clave de la API, para no tener que volver a pegarla.
    env_viejo = programa / ".env"
    env_nuevo = nueva / ".env"
    if env_viejo.exists() and not env_nuevo.exists():
        valores, _ = config.leer_env(env_viejo)
        if valores.get("ANTHROPIC_API_KEY"):
            shutil.copy2(env_viejo, env_nuevo)
            hecho.append(f"tu clave de la API copiada a {env_nuevo}{donde}")

    # 3. Los ajustes (dónde tienes Dwarf Fortress, cuál es tu fortaleza).
    ajustes_viejos = antigua / "ajustes.json"
    if ajustes_viejos.exists() and not (nueva / "ajustes.json").exists():
        shutil.copy2(ajustes_viejos, nueva / "ajustes.json")
        hecho.append(f"ajustes copiados{donde}")

    # 4. La base de datos: si viaja, no hay que reimportar 45 MB.
    if _copiar_bd(antigua / "db" / "prolegends.db", config.DB_PATH):
        hecho.append(f"base de datos copiada{donde}: no hace falta reimportar")

    # 5. Los XML, que pesan mucho: esos se mueven en vez de duplicarse.
    imports_viejos = antigua / "imports"
    if imports_viejos.is_dir():
        cuantos = _mover_ficheros(imports_viejos, config.IMPORTS_DIR, "*.xml")
        if cuantos:
            hecho.append(f"{cuantos} fichero(s) de export traídos{donde}")

    return hecho
