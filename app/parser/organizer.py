"""Ordenacion automatica de la carpeta data/imports/.

Dwarf Fortress nombra los exports con el nombre de la CARPETA de la partida
(region1, region4...), que no dice nada de que mundo es. Este modulo lee el
nombre real del mundo -que está en los primeros bytes del XML, asi que no hace
falta leerse los 45 MB- y deja los ficheros asi:

    data/imports/momuzosith/momuzosith-00101-07-24-legends.xml
    data/imports/momuzosith/momuzosith-00101-07-24-legends_plus.xml

Reglas de seguridad, porque aqui se tocan ficheros del usuario:

- Nunca se sobrescribe nada. Si el destino ya existe y es otro fichero, se deja
  como esta y se avisa.
- Los dos ficheros de un mismo export se mueven juntos o no se mueve ninguno.
- Nunca se borra nada.
- Si un fichero no es un export de legends, no se toca.
- Se puede pedir el plan sin aplicarlo, para verlo antes.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .discover import MAIN_SUFFIX, PLUS_SUFFIX
from .xmlstream import SanitizedXMLStream

CABECERA_BYTES = 65536  # de sobra: el nombre del mundo esta en la 3a línea

_RE_DF_WORLD = re.compile(r"<df_world[\s>]", re.IGNORECASE)
_RE_ETIQUETA = re.compile(r"<(/?)([A-Za-z_][\w.-]*)([^>]*?)(/?)>", re.DOTALL)


# --------------------------------------------------------------- cabecera
def leer_cabecera(path: Path) -> dict:
    """Lee solo el principio del XML y saca de ahí el nombre del mundo.

    Importa mucho coger el nombre del MUNDO y no el de la primera región que
    aparezca: dentro de <regions> hay un <name> por cada región, y en los
    exports que no traen nombre de mundo eso es lo primero que se encuentra.
    Por eso aquí solo se aceptan las etiquetas que cuelgan directamente de
    <df_world>.
    """
    datos = {"es_legends": False, "nombre": None, "altnombre": None, "error": None}
    try:
        stream = SanitizedXMLStream(path)
        try:
            texto = stream.read(CABECERA_BYTES).decode("utf-8", errors="replace")
        finally:
            stream.close()
    except OSError as exc:
        datos["error"] = str(exc)
        return datos

    inicio = _RE_DF_WORLD.search(texto)
    if not inicio:
        return datos
    datos["es_legends"] = True

    profundidad = 0            # 0 = justo dentro de <df_world>
    abierta = None             # etiqueta de primer nivel que está abierta
    desde = inicio.end()

    for m in _RE_ETIQUETA.finditer(texto, inicio.end()):
        es_cierre, etiqueta, _, auto_cierre = (
            m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        )

        if es_cierre:
            if profundidad == 1 and abierta == etiqueta:
                contenido = texto[desde:m.start()].strip()
                if etiqueta in ("name", "n") and not datos["nombre"]:
                    datos["nombre"] = contenido or None
                elif etiqueta == "altname" and not datos["altnombre"]:
                    datos["altnombre"] = contenido or None
                abierta = None
            profundidad -= 1
            if profundidad < 0:        # se acaba de cerrar <df_world>
                break
            continue

        if auto_cierre:                # etiqueta vacía tipo <deity/>
            continue

        profundidad += 1
        if profundidad == 1:
            abierta = etiqueta
            desde = m.end()
        if datos["nombre"] and datos["altnombre"]:
            break

    return datos


# ------------------------------------------------------------------ slug
def slug(texto: Optional[str], por_defecto: str = "mundo") -> str:
    """Convierte el nombre del mundo en algo valido como nombre de fichero.

    Los nombres de DF traen simbolos de CP437 (el sol, notas musicales) que no
    valen en un nombre de fichero en Windows, asi que se quitan.
    """
    if not texto:
        return por_defecto
    normal = unicodedata.normalize("NFKD", texto)
    ascii_ = normal.encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^A-Za-z0-9]+", "-", ascii_).strip("-").lower()
    limpio = re.sub(r"-{2,}", "-", limpio)[:48].strip("-")
    return limpio or por_defecto


# ------------------------------------------------------------------ plan
@dataclass
class Movimiento:
    origen: Path
    destino: Path
    motivo: str = ""

    @property
    def cambia(self) -> bool:
        return self.origen.resolve() != self.destino.resolve()


@dataclass
class GrupoPlan:
    """Un export: su fichero principal, su _plus y a donde van los dos."""
    clave: str
    mundo: Optional[str] = None
    slug_mundo: Optional[str] = None
    fecha: Optional[tuple[int, int, int]] = None
    movimientos: list[Movimiento] = field(default_factory=list)
    aplicable: bool = True
    aviso: str = ""

    @property
    def cambia(self) -> bool:
        return self.aplicable and any(m.cambia for m in self.movimientos)


def _partes(path: Path) -> Optional[tuple[str, str]]:
    """Devuelve (prefijo, sufijo) si el fichero es un export de legends."""
    nombre = path.name
    if nombre.endswith(PLUS_SUFFIX):
        return nombre[: -len(PLUS_SUFFIX)], PLUS_SUFFIX
    if nombre.endswith(MAIN_SUFFIX):
        return nombre[: -len(MAIN_SUFFIX)], MAIN_SUFFIX
    return None


def planificar(
    imports_dir: Path,
    en_carpetas: bool = True,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[list[GrupoPlan], list[str]]:
    """Calcula qué habría que renombrar y mover, sin tocar nada.

    Se parte de las PAREJAS que detecta el descubridor, no de los ficheros
    sueltos. Esto es importante: el fichero principal y el _plus del mismo
    export pueden anunciar nombres de mundo distintos (DFHack escribe en el
    _plus el nombre traducido), así que el mundo se decide una sola vez para
    la pareja y los dos ficheros acaban en la misma carpeta.
    """
    from .discover import discover

    imports_dir = Path(imports_dir)
    if not imports_dir.exists():
        return [], [f"La carpeta {imports_dir} no existe."]

    pares, avisos = discover(imports_dir)

    # Fechas ya conocidas de exports importados, por si el nombre no la trae.
    fechas_bd: dict[str, tuple[int, int, int]] = {}
    if conn is not None:
        try:
            for fila in conn.execute(
                """SELECT main_file, plus_file, game_year, game_month, game_day
                     FROM exports WHERE game_year IS NOT NULL"""
            ):
                fecha = (fila["game_year"], fila["game_month"] or 1, fila["game_day"] or 1)
                for clave in (fila["main_file"], fila["plus_file"]):
                    if clave:
                        fechas_bd[str(Path(clave).resolve())] = fecha
        except sqlite3.Error:
            pass

    grupos: list[GrupoPlan] = []
    for par in pares:
        ficheros = [f for f in (par.main, par.plus) if f is not None]
        if not ficheros:
            continue

        cabeceras = {f: leer_cabecera(f) for f in ficheros}
        error = next((c["error"] for c in cabeceras.values() if c["error"]), None)
        if error:
            avisos.append(f"No se ha podido leer '{par.prefix}': {error}")
            continue
        if not any(c["es_legends"] for c in cabeceras.values()):
            avisos.append(
                f"Se deja como está '{ficheros[0].name}': no parece un export de "
                "leyendas (no empieza por <df_world>)."
            )
            continue

        cab_main = cabeceras.get(par.main, {}) if par.main else {}
        cab_plus = cabeceras.get(par.plus, {}) if par.plus else {}
        # El nombre interno del principal manda; el _plus solo si el principal
        # no lo trae, que pasa en los exports sin DFHack.
        nombre = cab_main.get("nombre") or cab_plus.get("nombre")
        altnombre = cab_main.get("altnombre") or cab_plus.get("altnombre")
        if not nombre:
            nombre = altnombre
        nombre_slug = slug(nombre, por_defecto=slug(par.file_token or par.prefix, "mundo"))

        if par.game_year is not None:
            fecha = (par.game_year, par.game_month or 1, par.game_day or 1)
        else:
            fecha = next(
                (fechas_bd[str(f.resolve())] for f in ficheros
                 if str(f.resolve()) in fechas_bd),
                None,
            )

        grupo = GrupoPlan(
            clave=par.prefix, mundo=nombre, slug_mundo=nombre_slug, fecha=fecha
        )
        if not nombre:
            grupo.aviso = (
                "Este export no dice cómo se llama el mundo, así que se usa el "
                "nombre del fichero."
            )
        if fecha:
            base = f"{nombre_slug}-{fecha[0]:05d}-{fecha[1]:02d}-{fecha[2]:02d}"
        else:
            base = nombre_slug
            grupo.aviso = (
                "El nombre no lleva fecha y este export todavía no está importado, "
                "así que se queda sin ella. Vuelve a ordenar después de importarlo "
                "y se le pondrá."
            )

        carpeta = imports_dir / nombre_slug if en_carpetas else imports_dir
        for fichero in ficheros:
            sufijo = PLUS_SUFFIX if fichero is par.plus else MAIN_SUFFIX
            grupo.movimientos.append(
                Movimiento(fichero, carpeta / f"{base}{sufijo}")
            )
        grupos.append(grupo)

    # Comprobaciones de seguridad, ya con todos los destinos calculados.
    reservados: dict[str, Path] = {}
    for grupo in grupos:
        for mov in grupo.movimientos:
            if not mov.cambia:
                continue
            destino = str(mov.destino.resolve())
            if destino in reservados:
                grupo.aplicable = False
                grupo.aviso = (
                    f"Dos ficheros distintos querrían llamarse '{mov.destino.name}'. "
                    "No se toca ninguno de los dos."
                )
            reservados[destino] = mov.origen
            if mov.destino.exists() and mov.destino.resolve() != mov.origen.resolve():
                grupo.aplicable = False
                grupo.aviso = (
                    f"Ya existe un fichero llamado '{mov.destino.name}' y es otro "
                    "distinto. No se sobrescribe nada."
                )

    grupos.sort(key=lambda g: (g.slug_mundo or "", g.clave))
    for grupo in grupos:
        if grupo.aviso and not grupo.aplicable:
            avisos.append(grupo.aviso)
    return grupos, avisos


# --------------------------------------------------------------- aplicar
def aplicar(
    grupos: list[GrupoPlan],
    conn: Optional[sqlite3.Connection] = None,
    log=None,
) -> dict:
    """Ejecuta el plan. Cada export se mueve entero o no se mueve."""
    log = log or (lambda msg: None)
    movidos: list[dict] = []
    fallos: list[str] = []

    for grupo in grupos:
        if not grupo.cambia:
            continue
        hechos: list[Movimiento] = []
        try:
            for mov in grupo.movimientos:
                if not mov.cambia:
                    continue
                mov.destino.parent.mkdir(parents=True, exist_ok=True)
                if mov.destino.exists():
                    raise FileExistsError(f"'{mov.destino.name}' ya existe")
                mov.origen.replace(mov.destino)
                hechos.append(mov)
                log(f"  {mov.origen.name}  ->  {mov.destino.relative_to(mov.destino.parents[1])}")
                movidos.append({"de": str(mov.origen), "a": str(mov.destino)})
        except OSError as exc:
            # Deshacer lo de este export para no dejarlo a medias.
            for hecho in reversed(hechos):
                try:
                    hecho.destino.replace(hecho.origen)
                except OSError:
                    pass
                movidos = [m for m in movidos if m["a"] != str(hecho.destino)]
            fallos.append(f"{grupo.slug_mundo}: {exc}")
            continue

        if conn is not None:
            _actualizar_bd(conn, hechos, log)

    _limpiar_carpetas_vacias(grupos)
    return {"movidos": movidos, "fallos": fallos}


def _actualizar_bd(conn: sqlite3.Connection, hechos: list[Movimiento], log) -> None:
    """Reapunta los exports ya importados a su nueva ruta y nombre.

    Sin esto, renombrar un fichero ya importado haria que la aplicacion lo viera
    como uno nuevo y volviera a procesar los 45 MB.
    """
    from .discover import ExportPair

    for mov in hechos:
        partes = _partes(mov.destino)
        if partes is None:
            continue
        nuevo_prefijo = partes[0]
        fila = conn.execute(
            "SELECT id, main_file, plus_file FROM exports WHERE main_file = ? OR plus_file = ?",
            (str(mov.origen), str(mov.origen)),
        ).fetchone()
        if fila is None:
            continue
        principal = str(mov.destino) if fila["main_file"] == str(mov.origen) else fila["main_file"]
        plus = str(mov.destino) if fila["plus_file"] == str(mov.origen) else fila["plus_file"]
        par = ExportPair(
            prefix=nuevo_prefijo,
            main=Path(principal) if principal else None,
            plus=Path(plus) if plus and Path(plus).exists() else None,
        )
        try:
            huella = par.fingerprint()
        except OSError:
            continue
        conn.execute(
            """UPDATE exports SET prefix = ?, main_file = ?, plus_file = ?, fingerprint = ?
                WHERE id = ?""",
            (nuevo_prefijo, principal, plus, huella, fila["id"]),
        )
        log(f"  (la base de datos ya apunta al nombre nuevo, no se reimporta)")


def _limpiar_carpetas_vacias(grupos: list[GrupoPlan]) -> None:
    """Quita las carpetas que hayan quedado vacias al mover los ficheros."""
    candidatas = {m.origen.parent for g in grupos for m in g.movimientos}
    for carpeta in candidatas:
        try:
            if carpeta.is_dir() and not any(carpeta.iterdir()):
                carpeta.rmdir()
        except OSError:
            pass


def describir(grupos: list[GrupoPlan]) -> list[dict]:
    """El plan en forma de diccionarios, para la interfaz."""
    salida = []
    for grupo in grupos:
        salida.append(
            {
                "mundo": grupo.mundo,
                "carpeta": grupo.slug_mundo,
                "fecha": (
                    f"{grupo.fecha[0]:05d}-{grupo.fecha[1]:02d}-{grupo.fecha[2]:02d}"
                    if grupo.fecha else None
                ),
                "cambia": grupo.cambia,
                "aplicable": grupo.aplicable,
                "aviso": grupo.aviso,
                "ficheros": [
                    {
                        "de": m.origen.name,
                        "a": str(m.destino.relative_to(m.destino.parents[1])),
                        "cambia": m.cambia,
                    }
                    for m in grupo.movimientos
                ],
            }
        )
    return salida
