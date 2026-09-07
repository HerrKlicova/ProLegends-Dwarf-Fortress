"""Conexión con la carpeta de Dwarf Fortress.

Cuando exportas las leyendas, Dwarf Fortress deja los XML **en la misma carpeta
donde está el ejecutable**, mezclados con las DLL y los registros del juego:

    D:\\Steam\\steamapps\\common\\Dwarf Fortress\\
        Dwarf Fortress.exe
        region1-00103-10-15-legends.xml         (unos 45 MB)
        region1-00103-10-15-legends_plus.xml    (unos 13 MB)

Este módulo encuentra esa carpeta sola, enseña qué exports hay dentro y los trae
a data/imports/. Nunca toca los ficheros del juego salvo que pidas moverlos, y
por defecto los copia.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable, Optional

from . import ajustes, config
from .parser.discover import MAIN_SUFFIX, PLUS_SUFFIX, _PREFIX_RE
from .parser.organizer import leer_cabecera

EJECUTABLE = "Dwarf Fortress.exe"
# Señales de que una carpeta es la de Dwarf Fortress, por orden de fiabilidad.
SENYALES = (EJECUTABLE, "dwarfort.exe", "df", "dfhack.exe", "data")

AJUSTE_CARPETA = "carpeta_df"

# Imágenes que el juego exporta junto a las leyendas. No se usan todavía, pero
# conviene saber si están.
EXTENSIONES_MAPA = (".bmp", ".png")


# ------------------------------------------------------- dónde puede estar
def _rutas_steam() -> list[Path]:
    """Bibliotecas de Steam, sacadas del propio Steam cuando se puede."""
    bibliotecas: list[Path] = []
    raices: list[Path] = []

    if sys.platform.startswith("win"):
        try:
            import winreg  # type: ignore

            for colmena, clave in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            ):
                try:
                    with winreg.OpenKey(colmena, clave) as k:
                        for nombre in ("SteamPath", "InstallPath"):
                            try:
                                raices.append(Path(winreg.QueryValueEx(k, nombre)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
        for letra in "CDEFGH":
            raices.append(Path(f"{letra}:/Steam"))
            raices.append(Path(f"{letra}:/Program Files (x86)/Steam"))
            raices.append(Path(f"{letra}:/Program Files/Steam"))
    else:
        casa = Path.home()
        raices += [
            casa / ".steam/steam",
            casa / ".local/share/Steam",
            casa / "Library/Application Support/Steam",
        ]

    for raiz in raices:
        if not raiz.exists():
            continue
        bibliotecas.append(raiz)
        # libraryfolders.vdf lista las bibliotecas de otros discos.
        for vdf in (raiz / "steamapps/libraryfolders.vdf",
                    raiz / "config/libraryfolders.vdf"):
            if not vdf.exists():
                continue
            try:
                texto = vdf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for ruta in re.findall(r'"path"\s*"([^"]+)"', texto):
                bibliotecas.append(Path(ruta.replace("\\\\", "\\")))
    return bibliotecas


def _candidatas() -> list[Path]:
    """Carpetas donde merece la pena mirar, sin rastrear el disco entero."""
    vistas: list[Path] = []

    for biblioteca in _rutas_steam():
        vistas.append(biblioteca / "steamapps/common/Dwarf Fortress")

    casa = Path.home()
    sueltas = [
        casa / "Dwarf Fortress", casa / "Desktop/Dwarf Fortress",
        casa / "Escritorio/Dwarf Fortress", casa / "Documents/Dwarf Fortress",
        casa / "Documentos/Dwarf Fortress", casa / "Downloads/Dwarf Fortress",
        casa / "Descargas/Dwarf Fortress", casa / "Games/Dwarf Fortress",
        casa / "Juegos/Dwarf Fortress",
    ]
    if sys.platform.startswith("win"):
        for letra in "CDEFGH":
            disco = Path(f"{letra}:/")
            sueltas += [disco / "Dwarf Fortress", disco / "Games/Dwarf Fortress",
                        disco / "Juegos/Dwarf Fortress",
                        disco / "Program Files (x86)/Dwarf Fortress"]
    vistas += sueltas

    # Y una pasada superficial por las carpetas de juegos, por si la han
    # renombrado ("Dwarf Fortress 50.15", "DF classic"...).
    padres = [casa / "Games", casa / "Juegos", casa / "Desktop", casa / "Escritorio"]
    for biblioteca in _rutas_steam():
        padres.append(biblioteca / "steamapps/common")
    if sys.platform.startswith("win"):
        padres += [Path(f"{l}:/Games") for l in "CDEFGH"]
    for padre in padres:
        try:
            if not padre.is_dir():
                continue
            for hijo in padre.iterdir():
                if hijo.is_dir() and "dwarf" in hijo.name.lower():
                    vistas.append(hijo)
        except OSError:
            continue

    unicas: list[Path] = []
    ya: set[str] = set()
    for ruta in vistas:
        clave = str(ruta).lower()
        if clave not in ya:
            ya.add(clave)
            unicas.append(ruta)
    return unicas


def es_carpeta_df(carpeta: Path) -> bool:
    try:
        if not carpeta.is_dir():
            return False
        nombres = {p.name.lower() for p in carpeta.iterdir()}
    except OSError:
        return False
    if any(s.lower() in nombres for s in SENYALES[:4]):
        return True
    # O simplemente que haya exports de leyendas dentro.
    return any(n.endswith(MAIN_SUFFIX.lower()) for n in nombres)


def buscar() -> list[dict]:
    """Instalaciones de Dwarf Fortress encontradas, la mejor primero."""
    halladas: list[dict] = []
    for carpeta in _candidatas():
        if not es_carpeta_df(carpeta):
            continue
        pares = exports_en(carpeta)
        halladas.append(
            {
                "ruta": str(carpeta),
                "tiene_ejecutable": (carpeta / EJECUTABLE).exists(),
                "exports": len(pares),
                "ultimo": pares[-1]["prefijo"] if pares else None,
            }
        )
    # Primero las que tengan exports; entre esas, la que más tenga.
    halladas.sort(key=lambda h: (h["exports"] > 0, h["exports"], h["tiene_ejecutable"]),
                  reverse=True)
    return halladas


# ------------------------------------------------------- qué hay dentro
def exports_en(carpeta: Path) -> list[dict]:
    """Los pares de export que haya en esa carpeta, ordenados por fecha."""
    carpeta = Path(carpeta)
    try:
        ficheros = list(carpeta.iterdir())
    except OSError:
        return []

    pares: dict[str, dict] = {}
    for fichero in ficheros:
        if not fichero.is_file():
            continue
        nombre = fichero.name
        if nombre.endswith(PLUS_SUFFIX):
            prefijo, hueco = nombre[: -len(PLUS_SUFFIX)], "plus"
        elif nombre.endswith(MAIN_SUFFIX):
            prefijo, hueco = nombre[: -len(MAIN_SUFFIX)], "principal"
        else:
            continue
        entrada = pares.setdefault(
            prefijo,
            {"prefijo": prefijo, "principal": None, "plus": None,
             "anyo": None, "mes": None, "dia": None},
        )
        entrada[hueco] = fichero

    salida: list[dict] = []
    for prefijo, entrada in pares.items():
        m = _PREFIX_RE.match(prefijo)
        if m:
            entrada["anyo"] = int(m.group("year"))
            entrada["mes"] = int(m.group("month"))
            entrada["dia"] = int(m.group("day"))
        principal = entrada["principal"]
        plus = entrada["plus"]
        cabecera = leer_cabecera(principal or plus) if (principal or plus) else {}
        tamano = sum(f.stat().st_size for f in (principal, plus) if f)
        salida.append(
            {
                "prefijo": prefijo,
                "mundo": cabecera.get("nombre") or cabecera.get("altnombre"),
                "anyo": entrada["anyo"],
                "mes": entrada["mes"],
                "dia": entrada["dia"],
                "completo": bool(principal and plus),
                "principal": principal.name if principal else None,
                "plus": plus.name if plus else None,
                "tamano_mb": round(tamano / 1048576, 1),
                "ya_en_imports": _ya_esta(prefijo),
            }
        )
    salida.sort(key=lambda e: (e["anyo"] or 0, e["mes"] or 0, e["dia"] or 0, e["prefijo"]))
    return salida


def _ya_esta(prefijo: str) -> bool:
    """¿Está ya ese export en data/imports, con el nombre que sea?"""
    try:
        for fichero in config.IMPORTS_DIR.rglob("*" + MAIN_SUFFIX):
            if fichero.name.startswith(prefijo):
                return True
        # También puede estar ya renombrado por el organizador.
        for fichero in config.IMPORTS_DIR.rglob("*" + MAIN_SUFFIX):
            m = _PREFIX_RE.match(fichero.name[: -len(MAIN_SUFFIX)])
            n = _PREFIX_RE.match(prefijo)
            if m and n and (m.group("year"), m.group("month"), m.group("day")) == (
                n.group("year"), n.group("month"), n.group("day")
            ):
                return True
    except OSError:
        pass
    return False


def mapas_en(carpeta: Path) -> list[str]:
    """Imágenes de mapa que el juego haya dejado ahí. Aún no se usan."""
    try:
        return sorted(
            p.name for p in Path(carpeta).iterdir()
            if p.is_file() and p.suffix.lower() in EXTENSIONES_MAPA
        )[:60]
    except OSError:
        return []


# ------------------------------------------------------------- traerlos
def traer(carpeta: Path, prefijos: Iterable[str], mover: bool = False,
          log=None) -> dict:
    """Copia (o mueve) a data/imports los exports indicados."""
    log = log or (lambda m: None)
    carpeta = Path(carpeta)
    config.ensure_dirs()
    pedidos = set(prefijos)

    traidos: list[str] = []
    fallos: list[str] = []
    for export in exports_en(carpeta):
        if export["prefijo"] not in pedidos:
            continue
        origenes = [carpeta / n for n in (export["principal"], export["plus"]) if n]
        hechos: list[Path] = []
        try:
            for origen in origenes:
                destino = config.IMPORTS_DIR / origen.name
                if destino.exists() and destino.stat().st_size == origen.stat().st_size:
                    log(f"  ya estaba: {origen.name}")
                    continue
                log(f"  {'moviendo' if mover else 'copiando'} {origen.name} "
                    f"({origen.stat().st_size / 1048576:.0f} MB)...")
                shutil.copy2(origen, destino)
                hechos.append(destino)
            if mover:
                for origen in origenes:
                    try:
                        origen.unlink()
                    except OSError as exc:
                        log(f"  [aviso] no se ha podido borrar {origen.name}: {exc}")
            traidos.append(export["prefijo"])
        except OSError as exc:
            # Si falla a mitad, se deshace lo de este export.
            for hecho in hechos:
                try:
                    hecho.unlink()
                except OSError:
                    pass
            fallos.append(f"{export['prefijo']}: {exc}")
    return {"traidos": traidos, "fallos": fallos}


# ------------------------------------------------------------- recordar
def carpeta_recordada() -> Optional[Path]:
    guardada = ajustes.obtener(AJUSTE_CARPETA)
    if not guardada:
        return None
    carpeta = Path(guardada)
    return carpeta if carpeta.is_dir() else None


def recordar(carpeta: Path) -> None:
    ajustes.poner(AJUSTE_CARPETA, str(Path(carpeta)))


def olvidar() -> None:
    ajustes.olvidar(AJUSTE_CARPETA)


# ------------------------------------------- diálogo nativo de carpetas
def elegir_carpeta_a_mano() -> Optional[str]:
    """Abre el diálogo de carpetas del sistema.

    Funciona porque el servidor corre en tu propio ordenador. Se lanza en un
    proceso aparte a propósito: tkinter y un servidor web en el mismo proceso
    se llevan mal, y así un fallo del diálogo no puede tumbar la aplicación.
    """
    import subprocess

    guion = (
        "import tkinter, tkinter.filedialog as fd\n"
        "r = tkinter.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        "print(fd.askdirectory(title='Elige la carpeta de Dwarf Fortress') or '')\n"
    )
    try:
        salida = subprocess.run(
            [sys.executable, "-c", guion],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    elegida = (salida.stdout or "").strip().splitlines()
    ruta = elegida[-1].strip() if elegida else ""
    return ruta or None
