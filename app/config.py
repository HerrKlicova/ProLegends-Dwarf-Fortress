"""Configuracion y rutas del proyecto.

Todo lo que dependa del entorno se lee aqui, de forma que el resto del codigo
no tenga que saber donde vive nada. Las claves de API se leen del fichero .env
(ver .env.example) y nunca se escriben en el codigo.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
IMPORTS_DIR = DATA_DIR / "imports"
DB_DIR = DATA_DIR / "db"
DB_PATH = DB_DIR / "prolegends.db"
WEB_DIR = BASE_DIR / "web"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _load_dotenv() -> None:
    """Carga .env si existe. Usa python-dotenv si está disponible; si no, un
    parser minimo, para que el arranque nunca dependa de una libreria opcional."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path, override=False)
        return
    except Exception:
        pass
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


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
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_MAX_TOKENS = env_int("ANTHROPIC_MAX_TOKENS", 4000)

# --- Avisos del panel de fortaleza ---
DEFAULT_ALERT_RADIUS = env_int("PROLEGENDS_ALERT_RADIUS", 20)


def ensure_dirs() -> None:
    for directory in (DATA_DIR, IMPORTS_DIR, DB_DIR):
        directory.mkdir(parents=True, exist_ok=True)
