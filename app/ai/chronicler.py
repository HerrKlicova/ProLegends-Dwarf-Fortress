"""Llamada a la API de Anthropic para narrar la cronica.

Nunca se llama sola: siempre a peticion explicita del usuario, y el resultado
queda cacheado en SQLite para no pagar dos veces por el mismo texto.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import config
from ..errors import ProLegendsError
from . import almacen
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


def nombre_mundo(conn: sqlite3.Connection, world_id: int) -> str:
    fila = conn.execute("SELECT name FROM worlds WHERE id = ?", (world_id,)).fetchone()
    return (fila["name"] if fila else "") or f"mundo-{world_id}"


def cacheada(conn: sqlite3.Connection, world_id: int, ambito: dict) -> Optional[dict]:
    """La crónica ya guardada, si la hay. Vive en disco, no en la base de datos."""
    return almacen.leer(
        nombre_mundo(conn, world_id), ambito.get("tipo", ""), clave_ambito(ambito)
    )



def disponible() -> tuple[bool, str]:
    """Si se puede llamar a la API y, si no, exactamente por qué no."""
    estado = config.diagnostico_clave()
    ruta = estado["ruta"]

    if not estado["tiene_clave"]:
        if estado["mal_nombrados"]:
            despistado = estado["mal_nombrados"][0]
            return False, (
                f"Hay un fichero llamado '{Path(despistado).name}' en la carpeta del "
                "programa. Eso pasa cuando el Bloc de notas añade '.txt' al guardar. "
                f"Cámbiale el nombre a '.env' (sin nada detrás) y listo. Ruta: {despistado}"
            )
        if not estado["existe"]:
            return False, (
                f"No existe el fichero de configuración. Debería estar aquí: {ruta}. "
                "Vuelve a arrancar start.bat y se creará solo; después ábrelo con el "
                "Bloc de notas y pon ahí tu clave."
            )
        if estado["fallo_lectura"]:
            return False, (
                f"El fichero {ruta} existe pero {estado['fallo_lectura']}. Ábrelo con "
                "el Bloc de notas, y al guardar elige la codificación UTF-8."
            )
        if estado["linea_presente"]:
            # El tamaño y la fecha son la clave para distinguir dos cosas que se
            # confunden mucho: que el editor no haya guardado todavía, o que se
            # esté editando el .env de otra carpeta.
            sello = ""
            if estado["tamano"] is not None:
                sello = (
                    f" El fichero que he leído ocupa {estado['tamano']} caracteres y se "
                    f"guardó por última vez el {estado['modificado']}. Si tu editor te "
                    "dice que tiene más caracteres que eso, es que los cambios no están "
                    "guardados todavía: vuelve a él y pulsa Ctrl+S. Y comprueba que el "
                    "fichero que tienes abierto es justo ese y no el de otra carpeta."
                )
            return False, (
                f"En {ruta} está la línea ANTHROPIC_API_KEY= pero sin nada detrás. "
                f"Pega ahí la clave, justo después del igual, y guarda con Ctrl+S.{sello} "
                "No hace falta reiniciar: recarga la página y ya."
            )
        return False, (
            f"En {ruta} no aparece la línea ANTHROPIC_API_KEY. Añádela al final del "
            "fichero, con tu clave detrás del igual."
        )

    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, (
            "Falta el paquete 'anthropic'. Vuelve a ejecutar start.bat para instalarlo."
        )

    if estado["formato_raro"]:
        return True, (
            "Aviso: la clave no empieza por 'sk-ant-', que es como empiezan las de "
            "Anthropic. Si la crónica falla, revisa que la copiaste entera."
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
                "texto": previa["texto"],
                "titulo": previa.get("titulo"),
                "modelo": previa.get("modelo"),
                "creada": previa.get("generada"),
                "fichero": previa.get("fichero"),
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
    modelo = config.modelo_ia()

    import anthropic

    cliente = anthropic.Anthropic(api_key=config.clave_api())
    try:
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=config.max_tokens_ia(),
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

    fichero = almacen.guardar(
        nombre_mundo(conn, world_id), tipo, clave,
        {
            "titulo": contexto.get("titulo"),
            "texto": salida,
            "modelo": modelo,
            "creada": _now(),
            "tokens_entrada": getattr(uso, "input_tokens", None),
            "tokens_salida": getattr(uso, "output_tokens", None),
            "export_id": export_id,
        },
    )

    return {
        "texto": salida,
        "titulo": contexto.get("titulo"),
        "modelo": modelo,
        "creada": _now(),
        "fichero": str(fichero),
        "de_cache": False,
        "tokens": {
            "entrada": getattr(uso, "input_tokens", None),
            "salida": getattr(uso, "output_tokens", None),
        },
    }
