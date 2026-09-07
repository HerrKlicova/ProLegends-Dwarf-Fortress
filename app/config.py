"""Configuracion y rutas del proyecto.

Todo lo que dependa del entorno se lee aqui, de forma que el resto del codigo
no tenga que saber donde vive nada. Las claves de API se leen del fichero .env
(ver .env.example) y nunca se escriben en el codigo.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Carpeta antigua: dentro del propio programa. Se sigue mirando para poder
# rescatar lo que hubiera ahí de versiones anteriores.
DATA_DIR_ANTIGUA = BASE_DIR / "data"


def _documentos() -> Path:
    """La carpeta de documentos del usuario, se llame como se llame."""
    casa = Path.home()
    for nombre in ("Documents", "Documentos"):
        candidata = casa / nombre
        if candidata.is_dir():
            return candidata
    # OneDrive se lleva a veces los documentos a un sitio propio.
    for padre in (casa / "OneDrive", casa / "OneDrive - Personal"):
        for nombre in ("Documents", "Documentos"):
            if (padre / nombre).is_dir():
                return padre / nombre
    return casa


def carpeta_personal() -> Path:
    """Donde viven TUS cosas: exports, base de datos, crónicas y ajustes.

    Va fuera de la carpeta del programa a propósito. Así, cuando bajas una
    versión nueva de ProLegends, no tienes que mover nada: la carpeta del
    programa se puede borrar entera y volver a bajar, que tus crónicas, tu
    clave y tus mundos ya importados siguen donde estaban.

    Se puede cambiar con la variable de entorno PROLEGENDS_HOME, por si
    prefieres tenerlo todo en un pincho USB o en otro disco.
    """
    elegida = os.environ.get("PROLEGENDS_HOME", "").strip()
    if elegida:
        return Path(elegida).expanduser()
    return _documentos() / "ProLegends"


DATA_DIR = carpeta_personal()
IMPORTS_DIR = DATA_DIR / "imports"
DB_DIR = DATA_DIR / "db"
DB_PATH = DB_DIR / "prolegends.db"


# El Bloc de notas de Windows tiene la costumbre de anadir .txt al guardar, y
# de ofrecer codificaciones que no son UTF-8. Se contemplan las dos cosas.
_CODIFICACIONES = ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "latin-1")
_NOMBRES_ERRONEOS = (".env.txt", ".env.text", "env", "env.txt", ".env.ini", ".env.cfg")


def rutas_env() -> list[Path]:
    """Dónde se busca el .env, por orden.

    Primero el de la carpeta del programa, que es donde han estado siempre las
    instrucciones; después el de tu carpeta personal, que es el que sobrevive a
    las actualizaciones. Gana el primero que tenga una clave de verdad, así que
    el .env vacío que crea start.bat no tapa al bueno.
    """
    return [BASE_DIR / ".env", carpeta_personal() / ".env"]


def ruta_env() -> Path:
    """El .env que se está usando ahora mismo."""
    for candidata in rutas_env():
        valores, _ = leer_env(candidata)
        if valores.get("ANTHROPIC_API_KEY"):
            return candidata
    for candidata in rutas_env():
        if candidata.exists():
            return candidata
    return rutas_env()[0]


def env_mal_nombrados() -> list[Path]:
    """Ficheros que parecen un .env al que se le ha colado otro nombre."""
    carpetas = (BASE_DIR, carpeta_personal())
    return [
        carpeta / nombre
        for carpeta in carpetas
        for nombre in _NOMBRES_ERRONEOS
        if (carpeta / nombre).exists()
    ]


def leer_env(path: Optional[Path] = None) -> tuple[dict, str]:
    """Lee un fichero .env y devuelve (valores, motivo_del_fallo).

    Prueba varias codificaciones porque el fichero lo escribe una persona con
    el Bloc de notas, no un programa.
    """
    path = Path(path or ruta_env())
    if not path.exists():
        return {}, "no existe"

    try:
        crudo = path.read_bytes()
    except OSError as exc:
        return {}, f"no se ha podido leer: {exc}"

    texto = None
    for codificacion in _CODIFICACIONES:
        try:
            candidato = crudo.decode(codificacion)
        except (UnicodeDecodeError, LookupError):
            continue
        # Un UTF-16 leído como si fuese de un byte deja ceros por medio.
        if "\x00" in candidato:
            continue
        texto = candidato
        break
    if texto is None:
        return {}, "el fichero está en una codificación que no se entiende"

    valores: dict[str, str] = {}
    for linea in texto.splitlines():
        limpia = linea.strip().lstrip("\ufeff")
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'").strip()
        if clave:
            valores[clave] = valor
    return valores, ""


def ajuste(nombre: str, por_defecto: str = "") -> str:
    """Valor de un ajuste, releyendo el .env en el momento.

    Se relee cada vez a propósito: así, si cambias el .env, basta con recargar
    la página en el navegador; no hace falta cerrar y volver a abrir start.bat.
    El .env manda sobre las variables de entorno del sistema.
    """
    for candidata in rutas_env():
        valores, _ = leer_env(candidata)
        valor = valores.get(nombre)
        if valor:
            return valor
    return os.environ.get(nombre, por_defecto)


def ajuste_int(nombre: str, por_defecto: int) -> int:
    try:
        return int((ajuste(nombre) or "").strip() or por_defecto)
    except (TypeError, ValueError):
        return por_defecto


def _load_dotenv() -> None:
    """Vuelca el .env en las variables de entorno al arrancar.

    Sirve para las herramientas que leen del entorno; los ajustes propios de la
    aplicación se consultan con ajuste(), que relee el fichero cada vez.
    """
    for candidata in rutas_env():
        valores, _ = leer_env(candidata)
        for clave, valor in valores.items():
            if valor and clave not in os.environ:
                os.environ[clave] = valor


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


# --- Servidor ---
HOST = env("PROLEGENDS_HOST", "127.0.0.1")
PORT = env_int("PROLEGENDS_PORT", 8420)

# --- API de Anthropic (fase 2, crónicas narradas) ---
# Se leen con funciones y no con constantes para que un cambio en el .env se
# note sin tener que cerrar y volver a abrir el servidor.
MODELO_POR_DEFECTO = "claude-sonnet-5"


def clave_api() -> str:
    return ajuste("ANTHROPIC_API_KEY", "")


def modelo_ia() -> str:
    return ajuste("ANTHROPIC_MODEL", MODELO_POR_DEFECTO) or MODELO_POR_DEFECTO


def max_tokens_ia() -> int:
    return ajuste_int("ANTHROPIC_MAX_TOKENS", 4000)


def diagnostico_clave() -> dict:
    """Qué pasa exactamente con la clave, para poder decírselo al usuario."""
    ruta = ruta_env()
    valores, fallo = leer_env(ruta)
    despistados = env_mal_nombrados()
    clave = clave_api()
    tamano = None
    modificado = ""
    if ruta.exists():
        try:
            info = ruta.stat()
            tamano = info.st_size
            modificado = datetime.fromtimestamp(info.st_mtime).strftime(
                "%d/%m/%Y a las %H:%M:%S"
            )
        except OSError:
            pass

    estado = {
        "ruta": str(ruta),
        "existe": ruta.exists(),
        "tamano": tamano,
        "modificado": modificado,
        "clave": clave,
        "tiene_clave": bool(clave),
        "mal_nombrados": [str(x) for x in despistados],
        "fallo_lectura": fallo if ruta.exists() else "",
        "linea_presente": "ANTHROPIC_API_KEY" in valores,
        "formato_raro": bool(clave) and not clave.startswith("sk-ant-"),
    }
    return estado

# --- Avisos del panel de fortaleza ---
DEFAULT_ALERT_RADIUS = env_int("PROLEGENDS_ALERT_RADIUS", 20)


def ensure_dirs() -> None:
    for directory in (DATA_DIR, IMPORTS_DIR, DB_DIR):
        directory.mkdir(parents=True, exist_ok=True)
