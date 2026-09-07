"""Llamada a la API de Anthropic para narrar la cronica.

Nunca se llama sola: siempre a peticion explicita del usuario, y el resultado
queda cacheado en SQLite para no pagar dos veces por el mismo texto.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .. import config
from ..errors import ProLegendsError
from . import context as ctx

SISTEMA = (
    "Eres un cronista que redacta en castellano crónicas históricas a partir de los "
    "archivos de leyendas de Dwarf Fortress.\n"
    "Reglas estrictas:\n"
    "1. No inventes NADA. Usa unicamente los hechos que se te dan. Si un dato no "
    "aparece, no lo menciones ni lo supongas.\n"
    "2. Tono de crónica histórica antigua, sobrio y evocador, sin florituras vacias.\n"
    "3. Respeta los nombres propios tal cual aparecen, sin traducirlos.\n"
    "4. Ordena el relato cronológicamente y agrupa los hechos en parrafos con sentido.\n"
    "5. Si los hechos son escasos, escribe una crónica breve; no rellenes.\n"
    "6. Devuelve texto plano con parrafos, sin encabezados de Markdown ni listas."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clave_ambito(ambito: dict) -> str:
    tipo = ambito.get("tipo")
    if tipo == "anyos":
        return f"anyos:{int(ambito['desde'])}-{int(ambito['hasta'])}"
    if tipo == "figura":
        return f"figura:{int(ambito['hf_id'])}"
    if tipo == "fortaleza":
        return f"fortaleza:{int(ambito['site_id'])}"
    raise ProLegendsError("Ámbito de crónica desconocido.")


def cacheada(conn: sqlite3.Connection, world_id: int, ambito: dict) -> Optional[dict]:
    tipo = ambito.get("tipo")
    fila = conn.execute(
        """SELECT * FROM chronicles WHERE world_id = ? AND scope_type = ? AND scope_key = ?""",
        (world_id, tipo, clave_ambito(ambito)),
    ).fetchone()
    return dict(fila) if fila else None


def disponible() -> tuple[bool, str]:
    if not config.ANTHROPIC_API_KEY:
        env = config.BASE_DIR / ".env"
        if env.exists():
            return False, (
                f"Falta tu clave. Abre este fichero con el Bloc de notas: {env} — "
                "busca la línea que pone ANTHROPIC_API_KEY= y pega la clave justo "
                "detrás del igual, sin espacios ni comillas. Guarda y vuelve a "
                "arrancar start.bat."
            )
        return False, (
            f"No existe el fichero de configuración. Debería estar en {env}. "
            "Vuelve a arrancar start.bat y se creará solo; después ábrelo con el "
            "Bloc de notas y pon ahí tu clave."
        )
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, (
            "Falta el paquete 'anthropic'. Vuelve a ejecutar start.bat para instalarlo."
        )
    return True, ""


def generar(
    conn: sqlite3.Connection,
    world_id: int,
    export_id: int,
    ambito: dict,
    regenerar: bool = False,
) -> dict:
    clave = clave_ambito(ambito)
    tipo = ambito.get("tipo")

    if not regenerar:
        previa = cacheada(conn, world_id, ambito)
        if previa:
            return {
                "texto": previa["text"],
                "titulo": previa["title"],
                "modelo": previa["model"],
                "creada": previa["created_at"],
                "de_cache": True,
            }

    ok, motivo = disponible()
    if not ok:
        raise ProLegendsError(motivo)

    contexto = ctx.construir(conn, export_id, ambito)
    if not contexto or not contexto.get("hechos"):
        raise ProLegendsError(
            "No hay hechos registrados en ese ámbito, así que no hay nada que narrar."
        )
    texto_datos = ctx.a_texto(contexto)
    modelo = config.ANTHROPIC_MODEL

    import anthropic

    cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=config.ANTHROPIC_MAX_TOKENS,
            system=SISTEMA,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Redacta la crónica correspondiente a estos datos del archivo de "
                        "leyendas. Recuerda: solo lo que aparece aquí.\n\n" + texto_datos
                    ),
                }
            ],
        )
    except Exception as exc:  # la libreria tiene su propia jerarquía de errores
        raise ProLegendsError(
            "La llamada a la API de Anthropic ha fallado.", str(exc)
        ) from exc

    partes = [bloque.text for bloque in respuesta.content if getattr(bloque, "type", "") == "text"]
    salida = "\n\n".join(p.strip() for p in partes if p.strip())
    uso = getattr(respuesta, "usage", None)

    conn.execute(
        """INSERT INTO chronicles
             (world_id, export_id, scope_type, scope_key, model, context_hash,
              title, text, tokens_in, tokens_out, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(world_id, scope_type, scope_key) DO UPDATE SET
             export_id = excluded.export_id, model = excluded.model,
             context_hash = excluded.context_hash, title = excluded.title,
             text = excluded.text, tokens_in = excluded.tokens_in,
             tokens_out = excluded.tokens_out, created_at = excluded.created_at""",
        (
            world_id, export_id, tipo, clave, modelo,
            ctx.huella(texto_datos, modelo), contexto.get("titulo"), salida,
            getattr(uso, "input_tokens", None), getattr(uso, "output_tokens", None),
            _now(),
        ),
    )
    return {
        "texto": salida,
        "titulo": contexto.get("titulo"),
        "modelo": modelo,
        "creada": _now(),
        "de_cache": False,
        "tokens": {
            "entrada": getattr(uso, "input_tokens", None),
            "salida": getattr(uso, "output_tokens", None),
        },
    }
