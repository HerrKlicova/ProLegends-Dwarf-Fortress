"""Conexión con la carpeta de Dwarf Fortress.

La interfaz habla solo con estos endpoints; toda la lógica de buscar la
instalación y traerse los ficheros vive en `app/juego.py`.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body

from .. import juego
from ..errors import ProLegendsError

router = APIRouter(tags=["juego"])

# Estado de la copia en curso: la interfaz lo consulta para la barra.
_estado: dict = {"activo": False, "lineas": [], "resultado": None, "error": None}
_cerrojo = threading.Lock()


def _foto(carpeta: Optional[Path]) -> dict:
    """Todo lo que la interfaz necesita saber de una carpeta de juego."""
    if carpeta is None:
        return {
            "carpeta": None,
            "recordada": juego.ajustes.obtener(juego.AJUSTE_CARPETA),
            "valida": False,
            "exports": [],
            "mapas": [],
        }
    return {
        "carpeta": str(carpeta),
        "recordada": juego.ajustes.obtener(juego.AJUSTE_CARPETA),
        "valida": True,
        "tiene_ejecutable": (carpeta / juego.EJECUTABLE).exists(),
        "exports": juego.exports_en(carpeta),
        "mapas": juego.mapas_en(carpeta),
    }


@router.get("/juego")
def estado_juego():
    """Qué carpeta hay recordada y qué exports tiene dentro."""
    return _foto(juego.carpeta_recordada())


@router.get("/juego/buscar")
def buscar_instalaciones():
    """Busca Dwarf Fortress por los sitios habituales (Steam incluido)."""
    halladas = juego.buscar()
    return {"instalaciones": halladas}


@router.post("/juego/carpeta")
def fijar_carpeta(payload: dict = Body(default={})):
    """Recuerda la carpeta indicada, si de verdad parece la del juego."""
    ruta = (payload.get("ruta") or "").strip()
    if not ruta:
        raise ProLegendsError("No has indicado ninguna carpeta.")
    carpeta = Path(ruta)
    if not carpeta.is_dir():
        raise ProLegendsError(
            f"La carpeta '{ruta}' no existe.",
            "Comprueba la ruta; si la has copiado de otro sitio, pega la ruta completa.",
        )
    if not juego.es_carpeta_df(carpeta):
        raise ProLegendsError(
            f"En '{ruta}' no parece estar Dwarf Fortress.",
            "Se busca 'Dwarf Fortress.exe' o algún fichero -legends.xml dentro. "
            "Es la carpeta donde está el ejecutable del juego, no la del guardado.",
        )
    juego.recordar(carpeta)
    return _foto(carpeta)


@router.post("/juego/olvidar")
def olvidar_carpeta():
    juego.olvidar()
    return {"estado": "olvidada"}


@router.post("/juego/elegir")
def elegir_carpeta():
    """Abre el diálogo de carpetas del sistema y recuerda lo que elijas.

    Solo tiene sentido porque el servidor corre en tu propio ordenador: la
    ventana se abre en tu escritorio, no en el navegador.
    """
    ruta = juego.elegir_carpeta_a_mano()
    if not ruta:
        return {"estado": "cancelado", **_foto(juego.carpeta_recordada())}
    carpeta = Path(ruta)
    if not juego.es_carpeta_df(carpeta):
        return {
            "estado": "no_es_df",
            "elegida": str(carpeta),
            "aviso": "Ahí no se ve ni 'Dwarf Fortress.exe' ni ningún -legends.xml. "
                     "Aun así puedes usarla si sabes que es la buena.",
            **_foto(juego.carpeta_recordada()),
        }
    juego.recordar(carpeta)
    return {"estado": "ok", **_foto(carpeta)}


# ------------------------------------------------------------ traerlos
def _copiar(carpeta: Path, prefijos: list[str], mover: bool) -> None:
    lineas: list[str] = []

    def log(mensaje: str) -> None:
        texto = str(mensaje).strip()
        if texto:
            lineas.append(texto)
            del lineas[:-200]
        print(mensaje)

    try:
        log(f"Trayendo {len(prefijos)} export(s) desde {carpeta}...")
        resultado = juego.traer(carpeta, prefijos, mover=mover, log=log)
        log("Listo. Ahora ya se pueden importar.")
        with _cerrojo:
            _estado["resultado"] = resultado
            _estado["error"] = None
    except Exception as exc:  # pragma: no cover
        with _cerrojo:
            _estado["error"] = f"No se han podido copiar los ficheros: {exc}"
    finally:
        with _cerrojo:
            _estado["activo"] = False
            _estado["lineas"] = lineas


@router.post("/juego/traer")
def traer_exports(payload: dict = Body(default={})):
    """Copia a data/imports los exports elegidos. No importa nada todavía."""
    prefijos = [p for p in (payload.get("prefijos") or []) if p]
    if not prefijos:
        raise ProLegendsError("No has marcado ningún export para traer.")
    ruta = (payload.get("ruta") or "").strip()
    carpeta = Path(ruta) if ruta else juego.carpeta_recordada()
    if carpeta is None or not carpeta.is_dir():
        raise ProLegendsError(
            "No hay ninguna carpeta de Dwarf Fortress configurada.",
            "Búscala o elígela a mano antes de traer nada.",
        )
    with _cerrojo:
        if _estado["activo"]:
            return {"estado": "ya_en_marcha"}
        _estado.update({"activo": True, "lineas": [], "resultado": None, "error": None})
    hilo = threading.Thread(
        target=_copiar,
        args=(carpeta, prefijos, bool(payload.get("mover"))),
        daemon=True,
    )
    hilo.start()
    return {"estado": "en_marcha", "cuantos": len(prefijos)}


@router.get("/juego/traer/estado")
def estado_traida():
    with _cerrojo:
        return dict(_estado)
