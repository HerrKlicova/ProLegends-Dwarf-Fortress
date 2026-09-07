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


def migrar(log: Optional[Callable[[str], None]] = None) -> list[str]:
    """Lleva a la carpeta personal lo que quedara en la del programa."""
    log = log or (lambda mensaje: None)
    antigua = config.DATA_DIR_ANTIGUA
    nueva = config.DATA_DIR
    if nueva.resolve() == antigua.resolve() or not antigua.is_dir():
        return []

    config.ensure_dirs()
    hecho: list[str] = []

    # 1. Las crónicas: lo único que cuesta dinero y no se puede regenerar.
    #    Se copian, nunca se mueven: las de la carpeta vieja se quedan de
    #    respaldo por si acaso.
    viejas = antigua / "cronicas"
    if viejas.is_dir():
        cuantas = _copiar_carpeta(viejas, nueva / "cronicas")
        if cuantas:
            hecho.append(f"{cuantas} crónica(s) copiadas a {nueva / 'cronicas'}")

    # 2. La clave de la API, para no tener que volver a pegarla.
    env_viejo = config.BASE_DIR / ".env"
    env_nuevo = nueva / ".env"
    if env_viejo.exists() and not env_nuevo.exists():
        valores, _ = config.leer_env(env_viejo)
        if valores.get("ANTHROPIC_API_KEY"):
            shutil.copy2(env_viejo, env_nuevo)
            hecho.append(f"tu clave de la API copiada a {env_nuevo}")

    # 3. Los ajustes (dónde tienes Dwarf Fortress, cuál es tu fortaleza).
    ajustes_viejos = antigua / "ajustes.json"
    if ajustes_viejos.exists() and not (nueva / "ajustes.json").exists():
        shutil.copy2(ajustes_viejos, nueva / "ajustes.json")
        hecho.append("ajustes copiados")

    # 4. La base de datos: si viaja, no hay que reimportar 45 MB.
    if _copiar_bd(antigua / "db" / "prolegends.db", config.DB_PATH):
        hecho.append("base de datos copiada: no hace falta reimportar")

    # 5. Los XML, que pesan mucho: esos se mueven.
    imports_viejos = antigua / "imports"
    if imports_viejos.is_dir():
        cuantos = _mover_ficheros(imports_viejos, config.IMPORTS_DIR, "*.xml")
        if cuantos:
            hecho.append(f"{cuantos} fichero(s) de export movidos a {config.IMPORTS_DIR}")

    if hecho:
        log("")
        log(f"  Tus cosas ahora viven en {nueva}")
        for linea in hecho:
            log(f"    - {linea}")
        log("  Esa carpeta ya no se toca al actualizar ProLegends.")
    return hecho
