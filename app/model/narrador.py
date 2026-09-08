"""Convierte un evento del XML en una frase que se pueda leer.

Antes, la ficha de una figura decía:

    159   Hf died   attacker_civ_id: 1 · cause: STRUCK · hfid: 105 · slayer_hfid: 121

Y ahora dice:

    Año 159 — Iden Craftshailed murió por un golpe a manos de Uthhkos Lusbomith,
    en Kolluslan.

Dos reglas, por orden de importancia:

1. **No se inventa nada.** Si el evento no dice dónde pasó, la frase no dice
   dónde pasó. Si un identificador no tiene nombre, se omite esa parte en vez
   de rellenarla.
2. **No se esconde nada.** Un tipo de evento sin plantilla no desaparece: se
   narra con la fórmula genérica y se sigue pudiendo ver el dato en bruto.

Dwarf Fortress tiene cientos de tipos de evento. Aquí están cubiertos los más
frecuentes; el resto cae en la fórmula genérica, que también es legible.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Callable, Iterable, Optional

from . import diccionario as D

# Los nombres que puede tener cada cosa según la versión de DF y del evento.
ALIAS = {
    "hf": ("hfid", "hf_id", "histfig", "hist_figure_id", "hist_fig_id", "group_hfid",
           "target_hfid", "changee_hfid", "woundee_hfid", "student_hfid", "doer_hfid",
           "speaker_hfid", "trickster_hfid", "eater_hfid", "saboteur_hfid", "unit_id"),
    "otro": ("slayer_hfid", "wounder_hfid", "teacher_hfid", "changer_hfid",
             "corruptor_hfid", "snatcher_hfid", "interrogator_hfid", "victim_hfid",
             "instigator_hfid", "appointer_hfid", "hfid_target", "hf_target",
             "new_leader_hfid", "overthrown_hfid"),
    "sitio": ("site_id", "site", "stash_site", "site_id_1"),
    "entidad": ("entity_id", "entity", "civ_id", "civ", "site_civ_id",
                "trader_entity_id", "religion_id"),
    "atacante": ("attacker_civ_id", "attacker_enid", "contactor_enid"),
    "defensor": ("defender_civ_id", "defender_enid", "contacted_enid", "target_civ_id"),
    "artefacto": ("artifact_id", "artifact"),
    "estructura": ("structure_id", "structure"),
    "region": ("subregion_id", "region_id"),
}


def _texto(valor) -> str:
    if valor is None or valor is True:
        return ""
    return str(valor).strip()


class Contexto:
    """Los datos de un evento, ya con los nombres resueltos."""

    def __init__(self, fila: dict, datos: dict, nombres: dict):
        self.fila = fila
        self.d = datos
        self._n = nombres
        self.anyo = fila.get("year")
        self.tipo = _texto(fila.get("type"))

    # --- acceso a los identificadores, mirando primero la columna y luego el JSON
    def _id(self, papel: str) -> Optional[int]:
        columna = {"hf": "hfid", "otro": "slayer_hfid", "sitio": "site_id",
                   "entidad": "civ_id", "atacante": "attacker_civ_id",
                   "defensor": "defender_civ_id", "artefacto": "artifact_id",
                   "estructura": "structure_id", "region": "subregion_id"}.get(papel)
        if columna and self.fila.get(columna) is not None:
            return self.fila[columna]
        for clave in ALIAS.get(papel, ()):
            if clave in self.d:
                try:
                    return int(str(self.d[clave]).strip())
                except (TypeError, ValueError):
                    continue
        return None

    def _nombre(self, tabla: str, papel: str, clave_extra: Iterable[str] = ()) -> str:
        ident = self._id(papel)
        if ident is None:
            for clave in clave_extra:
                if clave in self.d:
                    try:
                        ident = int(str(self.d[clave]).strip())
                        break
                    except (TypeError, ValueError):
                        continue
        if ident is None:
            return ""
        return self._n.get(tabla, {}).get(ident, "")

    # --- los actores de la frase
    def quien(self, *extra) -> str:      return self._nombre("hf", "hf", extra)          # noqa: E704
    def otro(self, *extra) -> str:       return self._nombre("hf", "otro", extra)        # noqa: E704
    def sitio(self, *extra) -> str:      return self._nombre("sitio", "sitio", extra)    # noqa: E704
    def entidad(self, *extra) -> str:    return self._nombre("entidad", "entidad", extra)  # noqa: E704
    def atacante(self, *extra) -> str:   return self._nombre("entidad", "atacante", extra)  # noqa: E704
    def defensor(self, *extra) -> str:   return self._nombre("entidad", "defensor", extra)  # noqa: E704
    def artefacto(self, *extra) -> str:  return self._nombre("artefacto", "artefacto", extra)  # noqa: E704
    def estructura(self, *extra) -> str: return self._nombre("estructura", "estructura", extra)  # noqa: E704
    def region(self, *extra) -> str:     return self._nombre("region", "region", extra)  # noqa: E704

    def hf_por(self, *claves) -> str:
        """El nombre de una figura buscada por una clave concreta del JSON."""
        for clave in claves:
            if clave in self.d:
                try:
                    ident = int(str(self.d[clave]).strip())
                except (TypeError, ValueError):
                    continue
                nombre = self._n.get("hf", {}).get(ident, "")
                if nombre:
                    return nombre
        return ""

    def campo(self, *claves) -> str:
        for clave in claves:
            valor = _texto(self.d.get(clave))
            if valor:
                return valor
        return ""

    # --- trozos de frase que se repiten
    def en_lugar(self) -> str:
        sitio = self.sitio()
        if sitio:
            return f" en {sitio}"
        region = self.region()
        if region:
            return f" en {region}"
        return ""

    def alguien(self, nombre: str, respaldo: str = "alguien") -> str:
        return nombre or respaldo


# =========================================================== las plantillas
# Muertes en las que no interviene nadie: si el export trae además un matador,
# es ruido, y decir «murió de vejez a manos de Fulano» sería contradictorio. El
# dato sigue estando: se ve con el interruptor de «ver en bruto».
SIN_MATADOR = {"OLD_AGE", "STARVED", "THIRST", "INFECTION", "PUT_TO_REST",
               "QUIT", "VANISH", "COLD", "HEAT", "SUFFOCATED", "NONE"}


def _muerte(c: Contexto) -> str:
    quien = c.alguien(c.quien(), "Una figura sin nombre")
    bruta = c.campo("cause", "death_cause").upper()
    causa = D.muerte(c.campo("cause", "death_cause"))
    matador = "" if bruta in SIN_MATADOR else c.otro()
    raza = c.campo("slayer_race")
    if not matador and bruta not in SIN_MATADOR and raza and raza not in ("-1", "UNKNOWN"):
        matador = f"un {D.limpiar(raza).lower()}"

    frase = f"{quien} murió"
    if causa:
        frase += f" {causa}"
    if matador:
        frase += f" a manos de {matador}"
    return frase + c.en_lugar() + "."


def _vinculo_entidad(c: Contexto, alta: bool) -> str:
    quien = c.alguien(c.quien())
    entidad = c.entidad()
    tipo = D.vinculo_ent(c.campo("link", "link_type"))
    cargo = c.campo("position")
    if alta:
        if cargo:
            base = f"{quien} pasó a ser {D.cargo(cargo).lower()}"
            if entidad:
                base += f" de {entidad}"
        elif tipo:
            base = f"{quien} pasó a ser {tipo}"
            if entidad:
                base += f" de {entidad}"
        else:
            base = f"{quien} se unió"
            if entidad:
                base += f" a {entidad}"
    else:
        base = f"{quien} dejó de ser {tipo or 'miembro'}"
        if entidad:
            base += f" de {entidad}"
    return base + c.en_lugar() + "."


def _vinculo_sitio(c: Contexto, alta: bool) -> str:
    quien = c.alguien(c.quien())
    sitio = c.sitio()
    tipo = D.vinculo_sitio(c.campo("link_type", "link"))
    if alta:
        base = f"{quien} estableció allí su {tipo}" if tipo else f"{quien} se vinculó a un lugar"
    else:
        base = f"{quien} abandonó su {tipo}" if tipo else f"{quien} rompió su vínculo con un lugar"
    if sitio:
        base += f" en {sitio}" if not base.endswith("lugar") else f": {sitio}"
    return base + "."


def _vinculo_hf(c: Contexto, alta: bool) -> str:
    uno = c.alguien(c.quien("hf", "hfid"))
    dos = c.hf_por("hfid_target", "hf_target", "target_hfid") or c.otro()
    tipo = D.vinculo_hf(c.campo("link_type", "link"))
    if alta:
        if tipo and dos:
            return f"{uno} y {dos} pasaron a ser {tipo}." if tipo.endswith("e") \
                else f"{dos} pasó a ser {tipo} de {uno}."
        return f"{uno} y {dos or 'otra figura'} quedaron unidos."
    return f"{uno} y {dos or 'otra figura'} dejaron de ser {tipo or 'lo que eran'}."


def _estado(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    estado = c.campo("state")
    verbo = D.traducir(estado, D.ESTADOS_HF) if estado else ""
    if verbo and estado in D.ESTADOS_HF:
        return f"{quien} {verbo}{c.en_lugar()}."
    return f"{quien} cambió de vida{(' (' + D.limpiar(estado).lower() + ')') if estado else ''}{c.en_lugar()}."


def _oficio(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    nuevo = D.profesion(c.campo("new_job"))
    viejo = D.profesion(c.campo("old_job"))
    if nuevo and viejo:
        return f"{quien} dejó la {viejo} y se dedicó a la {nuevo}{c.en_lugar()}."
    if nuevo:
        return f"{quien} se dedicó a la {nuevo}{c.en_lugar()}."
    return f"{quien} cambió de oficio{c.en_lugar()}."


def _fundacion(c: Contexto) -> str:
    sitio = c.sitio() or "un asentamiento"
    quien = c.entidad()
    constructor = c.hf_por("builder_hfid", "builder_hf")
    if quien:
        frase = f"{quien} fundó {sitio}"
    else:
        frase = f"Se fundó {sitio}"
    if constructor:
        frase += f", de la mano de {constructor}"
    return frase + "."


def _destruccion(c: Contexto) -> str:
    sitio = c.sitio() or "un asentamiento"
    atacante = c.atacante()
    defensor = c.defensor()
    frase = f"{atacante} arrasó {sitio}" if atacante else f"{sitio} quedó arrasado"
    if defensor:
        frase += f", que era de {defensor}"
    return frase + "."


def _conquista(c: Contexto) -> str:
    sitio = c.sitio() or "un asentamiento"
    atacante = c.atacante()
    defensor = c.defensor()
    frase = f"{atacante} tomó {sitio}" if atacante else f"{sitio} cambió de manos"
    if defensor:
        frase += f", arrebatándoselo a {defensor}"
    return frase + "."


def _ataque(c: Contexto) -> str:
    sitio = c.sitio() or "un asentamiento"
    atacante = c.atacante() or "un ejército"
    defensor = c.defensor()
    general = c.hf_por("attacker_general_hfid")
    frase = f"{atacante} atacó {sitio}"
    if defensor:
        frase += f", defendido por {defensor}"
    if general:
        frase += f", con {general} al mando"
    return frase + "."


def _hf_destruye(c: Contexto) -> str:
    quien = c.alguien(c.quien(), "Una bestia")
    sitio = c.sitio() or "un asentamiento"
    return f"{quien} destruyó {sitio}."


def _entidad_creada(c: Contexto) -> str:
    entidad = c.entidad() or "un nuevo grupo"
    return f"Se fundó {entidad}{c.en_lugar()}."


def _estructura_creada(c: Contexto) -> str:
    estructura = c.estructura()
    entidad = c.entidad()
    quien = c.hf_por("builder_hf", "builder_hfid")
    base = f"Se construyó {estructura}" if estructura else "Se levantó una construcción"
    if quien:
        base += f", obra de {quien}"
    elif entidad:
        base += f", obra de {entidad}"
    return base + c.en_lugar() + "."


def _artefacto(verbo: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        arte = c.artefacto() or "un artefacto"
        quien = c.quien() or c.hf_por("hist_figure_id", "unit_id")
        if quien:
            return f"{quien} {verbo} {arte}{c.en_lugar()}."
        return f"{arte}: {verbo}{c.en_lugar()}."
    return plantilla


def _artefacto_creado(c: Contexto) -> str:
    arte = c.artefacto() or "un artefacto"
    quien = c.quien() or c.hf_por("hist_figure_id", "unit_id")
    if quien:
        return f"{quien} creó {arte}{c.en_lugar()}."
    return f"Se creó {arte}{c.en_lugar()}."


def _obra_escrita(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("hist_figure_id", "hfid"), "Alguien")
    return f"{quien} compuso una obra escrita{c.en_lugar()}."


def _forma_creada(que: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        quien = c.alguien(c.hf_por("hist_figure_id", "hfid"), "Alguien")
        return f"{quien} creó una nueva forma de {que}{c.en_lugar()}."
    return plantilla


def _aprende_secreto(c: Contexto) -> str:
    alumno = c.alguien(c.hf_por("student_hfid", "hfid"))
    maestro = c.hf_por("teacher_hfid")
    secreto = D.secreto(c.campo("secret_text", "interaction"))
    frase = f"{alumno} aprendió {secreto or 'un secreto prohibido'}"
    if maestro:
        frase += f" de {maestro}"
    return frase + c.en_lugar() + "."


def _objetivo_secreto(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    meta = D.objetivo(c.campo("secret_goal", "goal"))
    return f"{quien} se propuso en secreto {meta or 'un objetivo oscuro'}."


def _interaccion(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("doer_hfid", "hfid"))
    objetivo = c.hf_por("target_hfid")
    if objetivo:
        return f"{quien} usó un poder sobrenatural sobre {objetivo}{c.en_lugar()}."
    return f"{quien} usó un poder sobrenatural{c.en_lugar()}."


def _mascota(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("group_hfid", "hfid"))
    return f"{quien} consiguió un animal de compañía{c.en_lugar()}."


def _combate_simple(c: Contexto) -> str:
    uno = c.alguien(c.hf_por("group_1_hfid", "hfid"))
    dos = c.hf_por("group_2_hfid")
    subtipo = D.limpiar(c.campo("subtype")).lower()
    if dos:
        return f"{uno} y {dos} se enfrentaron{(' (' + subtipo + ')') if subtipo else ''}{c.en_lugar()}."
    return f"{uno} entró en combate{c.en_lugar()}."


def _herida(c: Contexto) -> str:
    herido = c.alguien(c.hf_por("woundee_hfid", "hfid"))
    autor = c.hf_por("wounder_hfid")
    parte = D.limpiar(c.campo("body_part")).lower()
    frase = f"{herido} resultó herido"
    if autor:
        frase += f" por {autor}"
    if parte:
        frase += f" en {parte}"
    return frase + c.en_lugar() + "."


def _resucitado(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    if _texto(c.d.get("ghost")):
        return f"{quien} volvió como fantasma{c.en_lugar()}."
    return f"{quien} volvió de entre los muertos{c.en_lugar()}."


def _batalla_campal(c: Contexto) -> str:
    atacante = c.atacante() or "un ejército"
    defensor = c.defensor() or "otro"
    return f"{atacante} y {defensor} libraron una batalla{c.en_lugar()}."


def _paz(aceptada: bool) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        uno = c.entidad("source") or c.atacante()
        dos = c.defensor() or ""
        verbo = "aceptaron la paz" if aceptada else "rechazaron la paz"
        if uno and dos:
            return f"{uno} y {dos} {verbo}."
        return f"Se {'firmó' if aceptada else 'rompió'} un acuerdo de paz."
    return plantilla


def _ley(c: Contexto) -> str:
    entidad = c.entidad() or "un gobierno"
    quien = c.hf_por("hist_figure_id", "hfid")
    anyade = c.campo("law_add")
    quita = c.campo("law_remove")
    if anyade:
        frase = f"{entidad} promulgó una ley ({D.limpiar(anyade).lower()})"
    elif quita:
        frase = f"{entidad} derogó una ley ({D.limpiar(quita).lower()})"
    else:
        frase = f"{entidad} cambió sus leyes"
    if quien:
        frase += f", por decisión de {quien}"
    return frase + "."


def _robo(c: Contexto) -> str:
    quien = c.hf_por("histfig", "hfid")
    objeto = D.limpiar(c.campo("item_type", "item")).lower()
    frase = f"{quien} robó" if quien else "Hubo un robo de"
    frase += f" {objeto}" if objeto else " un objeto"
    return frase + c.en_lugar() + "."


def _mercader(c: Contexto) -> str:
    entidad = c.entidad("trader_entity_id", "trader_civ_id")
    frase = f"{entidad} envió una caravana" if entidad else "Llegó una caravana"
    return frase + c.en_lugar() + "."


def _nuevo_lider(c: Contexto) -> str:
    lider = c.hf_por("new_leader_hfid")
    sitio = c.sitio()
    atacante = c.atacante()
    frase = f"{lider} tomó el mando" if lider else "Hubo un cambio de mando"
    if sitio:
        frase += f" de {sitio}"
    if atacante:
        frase += f", en nombre de {atacante}"
    return frase + "."


def _sitio_simple(verbo: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        sitio = c.sitio() or "un asentamiento"
        entidad = c.entidad()
        frase = f"{sitio} {verbo}"
        if entidad:
            frase += f" ({entidad})"
        return frase + "."
    return plantilla


def _saqueo(c: Contexto) -> str:
    sitio = c.sitio() or "un asentamiento"
    atacante = c.atacante()
    return (f"{atacante} saqueó {sitio}." if atacante
            else f"{sitio} fue saqueado.")


def _estructura_verbo(verbo: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        estructura = c.estructura() or "una construcción"
        quien = c.quien() or c.entidad()
        if quien:
            return f"{quien} {verbo} {estructura}{c.en_lugar()}."
        return f"{estructura}: {verbo}{c.en_lugar()}."
    return plantilla


def _conocimiento(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    saber = D.limpiar(c.campo("knowledge")).lower()
    primero = _texto(c.d.get("first"))
    frase = f"{quien} descubrió {saber or 'un nuevo conocimiento'}"
    if primero:
        frase += ", y fue la primera vez que alguien lo hacía"
    return frase + "."


def _cumbre(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("group_hfid", "hfid"))
    return f"{quien} coronó una cumbre."


def _devorado(c: Contexto) -> str:
    comensal = c.alguien(c.hf_por("eater_hfid"), "Una bestia")
    victima = c.hf_por("victim_hfid")
    raza = D.limpiar(c.campo("race")).lower()
    presa = victima or (f"un {raza}" if raza else "a alguien")
    return f"{comensal} devoró {presa}{c.en_lugar()}."


def _identidad(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("trickster_hfid", "hfid"))
    return f"{quien} adoptó una identidad falsa{c.en_lugar()}."


def _cambio_raza(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("changee_hfid", "hfid"))
    autor = c.hf_por("changer_hfid")
    vieja = D.limpiar(c.campo("old_race")).lower()
    nueva = D.limpiar(c.campo("new_race")).lower()
    frase = f"{quien} dejó de ser {vieja} y pasó a ser {nueva}" if vieja and nueva \
        else f"{quien} cambió de naturaleza"
    if autor:
        frase += f", por obra de {autor}"
    return frase + "."


def _intriga(c: Contexto) -> str:
    corruptor = c.alguien(c.hf_por("corruptor_hfid"))
    objetivo = c.hf_por("target_hfid")
    metodo = D.limpiar(c.campo("method")).lower()
    frase = f"{corruptor} tejió una intriga"
    if objetivo:
        frase += f" con {objetivo}"
    if metodo:
        frase += f" ({metodo})"
    return frase + c.en_lugar() + "."


def _reputacion(c: Contexto) -> str:
    uno = c.alguien(c.hf_por("hfid1", "hfid"))
    dos = c.hf_por("hfid2")
    return f"{uno} y {dos or 'otra figura'} se ganaron fama mutua{c.en_lugar()}."


def _entidad_sitio(verbo: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        entidad = c.entidad() or "un grupo"
        sitio = c.sitio()
        return f"{entidad} {verbo}" + (f" {sitio}" if sitio else "") + "."
    return plantilla


def _expulsion(c: Contexto) -> str:
    entidad = c.entidad() or "un gobierno"
    quien = c.quien()
    return f"{entidad} expulsó a {quien or 'alguien'}{c.en_lugar()}."


def _esclavo(liberado: bool) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        quien = c.alguien(c.quien())
        otro = c.otro()
        verbo = "recuperó la libertad" if liberado else "fue reducido a esclavitud"
        frase = f"{quien} {verbo}"
        if otro and not liberado:
            frase += f" por {otro}"
        elif otro:
            frase += f" gracias a {otro}"
        return frase + c.en_lugar() + "."
    return plantilla


def _secuestro(c: Contexto) -> str:
    victima = c.alguien(c.quien())
    raptor = c.hf_por("snatcher_hfid") or c.otro()
    frase = f"{victima} fue secuestrado"
    if raptor:
        frase += f" por {raptor}"
    return frase + c.en_lugar() + "."


def _interrogatorio(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("target_hfid", "hfid"))
    autor = c.hf_por("interrogator_hfid")
    frase = f"{quien} fue interrogado"
    if autor:
        frase += f" por {autor}"
    return frase + c.en_lugar() + "."


def _condena(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("target_hfid", "hfid"))
    delito = D.limpiar(c.campo("crime")).lower()
    return f"{quien} fue condenado" + (f" por {delito}" if delito else "") + c.en_lugar() + "."


def _celebracion(que: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        entidad = c.entidad()
        frase = f"Se celebró {que}"
        if entidad:
            frase += f", organizada por {entidad}"
        return frase + c.en_lugar() + "."
    return plantilla


def _apuesta(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    return f"{quien} se jugó su dinero{c.en_lugar()}."


def _primer_contacto(c: Contexto) -> str:
    uno = c.atacante() or c.entidad()
    dos = c.defensor()
    if uno and dos:
        return f"{uno} y {dos} se conocieron por primera vez{c.en_lugar()}."
    return f"Dos pueblos se conocieron por primera vez{c.en_lugar()}."


def _ciudad_santa(c: Contexto) -> str:
    sitio = c.sitio() or "un lugar"
    entidad = c.entidad()
    frase = f"{sitio} fue declarada ciudad santa"
    if entidad:
        frase += f" de {entidad}"
    return frase + "."


def _derrocamiento(c: Contexto) -> str:
    entidad = c.entidad() or "un gobierno"
    caido = c.hf_por("overthrown_hfid")
    instigador = c.hf_por("instigator_hfid")
    frase = f"{entidad} fue derrocado"
    if caido:
        frase += f", y {caido} perdió el poder"
    if instigador:
        frase += f", por instigación de {instigador}"
    return frase + c.en_lugar() + "."


def _levantamiento(c: Contexto) -> str:
    sitio = c.sitio() or "un asentamiento"
    contra = c.defensor() or c.entidad()
    frase = f"Estalló un levantamiento en {sitio}"
    if contra:
        frase += f" contra {contra}"
    return frase + "."


def _sabotaje(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("saboteur_hfid", "hfid"))
    objetivo = c.hf_por("target_hfid")
    frase = f"{quien} saboteó los planes"
    if objetivo:
        frase += f" de {objetivo}"
    return frase + c.en_lugar() + "."


def _rezo(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    estructura = c.estructura()
    return f"{quien} rezó" + (f" en {estructura}" if estructura else "") + c.en_lugar() + "."


def _predica(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("speaker_hfid", "hfid"))
    tema = D.limpiar(c.campo("topic")).lower()
    return f"{quien} predicó" + (f" sobre {tema}" if tema else "") + c.en_lugar() + "."


def _juerga(c: Contexto) -> str:
    quien = c.alguien(c.hf_por("group_hfid", "hfid"))
    return f"{quien} se corrió una juerga{c.en_lugar()}."


def _honor(c: Contexto) -> str:
    quien = c.alguien(c.quien())
    entidad = c.entidad()
    return f"{quien} recibió un honor" + (f" de {entidad}" if entidad else "") + "."


def _cargo_creado(c: Contexto) -> str:
    entidad = c.entidad() or "un gobierno"
    cargo = D.cargo(c.campo("position")).lower()
    return f"{entidad} creó el cargo de {cargo or 'un nuevo puesto'}."


def _capa_profunda(c: Contexto) -> str:
    entidad = c.entidad() or "unos excavadores"
    return f"{entidad} perforó hasta las cavernas{c.en_lugar()}."


def _obra_maestra(que: str) -> Callable[[Contexto], str]:
    def plantilla(c: Contexto) -> str:
        quien = c.alguien(c.quien())
        return f"{quien} hizo una obra maestra de {que}{c.en_lugar()}."
    return plantilla


def _diplomatico(c: Contexto) -> str:
    entidad = c.entidad() or "una civilización"
    return f"{entidad} perdió a su diplomático{c.en_lugar()}."


def _acuerdo(c: Contexto) -> str:
    motivo = D.limpiar(c.campo("reason")).lower()
    return "Se cerró un acuerdo" + (f" ({motivo})" if motivo else "") + c.en_lugar() + "."


def _cadaver(c: Contexto) -> str:
    entidad = c.entidad()
    frase = f"{entidad} profanó los cadáveres de los caídos" if entidad \
        else "Se profanaron los cadáveres de los caídos"
    return frase + c.en_lugar() + "."


def _reencuentro(c: Contexto) -> str:
    uno = c.alguien(c.quien())
    dos = c.otro()
    return f"{uno} y {dos or 'un viejo conocido'} se reencontraron{c.en_lugar()}."


PLANTILLAS: dict[str, Callable[[Contexto], str]] = {
    "hf died": _muerte,
    "add hf entity link": lambda c: _vinculo_entidad(c, True),
    "remove hf entity link": lambda c: _vinculo_entidad(c, False),
    "add hf site link": lambda c: _vinculo_sitio(c, True),
    "remove hf site link": lambda c: _vinculo_sitio(c, False),
    "add hf hf link": lambda c: _vinculo_hf(c, True),
    "remove hf hf link": lambda c: _vinculo_hf(c, False),
    "change hf state": _estado,
    "change hf job": _oficio,
    "created site": _fundacion,
    "site created": _fundacion,
    "destroyed site": _destruccion,
    "site taken over": _conquista,
    "attacked site": _ataque,
    "hf attacked site": _ataque,
    "hf destroyed site": _hf_destruye,
    "entity created": _entidad_creada,
    "created structure": _estructura_creada,
    "structure created": _estructura_creada,
    "created world construction": lambda c: (
        f"Se terminó una gran obra: {D.construccion(c.campo('type'))}"
        f"{c.en_lugar()}."),
    "artifact created": _artefacto_creado,
    "created artifact": _artefacto_creado,
    "artifact stored": _artefacto("guardó"),
    "artifact possessed": _artefacto("se apoderó de"),
    "artifact claim formed": _artefacto("reclamó"),
    "artifact lost": _artefacto("perdió"),
    "artifact found": _artefacto("encontró"),
    "artifact recovered": _artefacto("recuperó"),
    "artifact given": _artefacto("entregó"),
    "artifact destroyed": _artefacto("destruyó"),
    "artifact copied": _artefacto("copió"),
    "artifact transformed": _artefacto("transformó"),
    "artifact stored in structure": _artefacto("depositó"),
    "written content composed": _obra_escrita,
    "poetic form created": _forma_creada("poesía"),
    "musical form created": _forma_creada("música"),
    "dance form created": _forma_creada("danza"),
    "hf learns secret": _aprende_secreto,
    "hf gains secret goal": _objetivo_secreto,
    "hf does interaction": _interaccion,
    "hf new pet": _mascota,
    "hf simple battle event": _combate_simple,
    "hf wounded": _herida,
    "hf revived": _resucitado,
    "field battle": _batalla_campal,
    "peace accepted": _paz(True),
    "peace rejected": _paz(False),
    "entity law": _ley,
    "item stolen": _robo,
    "merchant": _mercader,
    "new site leader": _nuevo_lider,
    "site abandoned": _sitio_simple("quedó abandonado"),
    "site died": _sitio_simple("se apagó del todo"),
    "site retired": _sitio_simple("quedó en desuso"),
    "site surrendered": _sitio_simple("se rindió"),
    "site dispute": _sitio_simple("entró en disputa"),
    "plundered site": _saqueo,
    "reclaim site": _sitio_simple("volvió a ser habitado"),
    "razed structure": _estructura_verbo("arrasó"),
    "hf razed structure": _estructura_verbo("arrasó"),
    "hf profaned structure": _estructura_verbo("profanó"),
    "hf disturbed structure": _estructura_verbo("perturbó"),
    "replaced structure": _estructura_verbo("reconstruyó"),
    "knowledge discovered": _conocimiento,
    "hf reach summit": _cumbre,
    "creature devoured": _devorado,
    "assume identity": _identidad,
    "impersonate hf": _identidad,
    "change creature type": _cambio_raza,
    "changed creature type": _cambio_raza,
    "hfs formed intrigue relationship": _intriga,
    "hfs formed reputation relationship": _reputacion,
    "entity searched site": _entidad_sitio("registró"),
    "entity rampaged in site": _entidad_sitio("sembró el caos en"),
    "entity fled site": _entidad_sitio("huyó de"),
    "entity relocate": _entidad_sitio("se trasladó a"),
    "entity incorporated": _entidad_sitio("fue absorbido en"),
    "entity dissolved": lambda c: f"{c.entidad() or 'Un grupo'} se disolvió{c.en_lugar()}.",
    "entity alliance formed": lambda c: (
        f"{c.atacante() or c.entidad() or 'Dos pueblos'} selló una alianza"
        f"{(' con ' + c.defensor()) if c.defensor() else ''}."),
    "entity primary criminals": _entidad_sitio("se echó al crimen en"),
    "entity expels hf": _expulsion,
    "sneak into site": _entidad_sitio("se coló en"),
    "spotted leaving site": _entidad_sitio("fue visto saliendo de"),
    "hf enslaved": _esclavo(False),
    "hf freed": _esclavo(True),
    "hf abducted": _secuestro,
    "hf ransomed": lambda c: f"{c.alguien(c.quien())} fue rescatado a cambio de un pago{c.en_lugar()}.",
    "hf interrogated": _interrogatorio,
    "hf convicted": _condena,
    "competition": _celebracion("una competición"),
    "performance": _celebracion("una actuación"),
    "ceremony": _celebracion("una ceremonia"),
    "procession": _celebracion("una procesión"),
    "gamble": _apuesta,
    "trade": _mercader,
    "first contact": _primer_contacto,
    "holy city declaration": _ciudad_santa,
    "entity overthrown": _derrocamiento,
    "insurrection started": _levantamiento,
    "sabotage": _sabotaje,
    "hf prayed inside structure": _rezo,
    "hf preach": _predica,
    "hf carouse": _juerga,
    "add hf entity honor": _honor,
    "create entity position": _cargo_creado,
    "entity breach feature layer": _capa_profunda,
    "masterpiece item": _obra_maestra("artesanía"),
    "masterpiece engraving": _obra_maestra("grabado"),
    "masterpiece food": _obra_maestra("cocina"),
    "masterpiece dye": _obra_maestra("tintura"),
    "masterpiece arch": _obra_maestra("arquitectura"),
    "masterpiece arch design": _obra_maestra("arquitectura"),
    "masterpiece arch constructed": _obra_maestra("arquitectura"),
    "masterpiece item improvement": _obra_maestra("orfebrería"),
    "masterpiece lost": lambda c: f"Se perdió una obra maestra{c.en_lugar()}.",
    "diplomat lost": _diplomatico,
    "agreement formed": _acuerdo,
    "agreement concluded": _acuerdo,
    "agreement made": _acuerdo,
    "agreement rejected": lambda c: f"Se rechazó un acuerdo{c.en_lugar()}.",
    "agreement void": lambda c: f"Un acuerdo quedó sin efecto{c.en_lugar()}.",
    "body abused": _cadaver,
    "hf reunion": _reencuentro,
    "hf confronted": lambda c: f"{c.alguien(c.quien())} se vio en un aprieto{c.en_lugar()}.",
    "hf travel": lambda c: f"{c.alguien(c.quien())} se puso en camino{c.en_lugar()}.",
    "regionpop incorporated into entity": lambda c: (
        f"{c.entidad() or 'Un pueblo'} incorporó a la gente de la comarca{c.en_lugar()}."),
    "hf recruited unit type for entity": lambda c: (
        f"{c.alguien(c.quien())} reclutó tropas"
        f"{(' para ' + c.entidad()) if c.entidad() else ''}{c.en_lugar()}."),
}


# ------------------------------------------------------------- fórmula genérica
def generica(c: Contexto) -> str:
    """Para los tipos que todavía no tienen plantilla propia.

    No inventa: pone el suceso tal como se llama y le engancha los actores que
    haya podido resolver. Es feo, pero es cierto y se lee.
    """
    partes = []
    quien = c.quien()
    if quien:
        partes.append(quien)
    suceso = D.limpiar(c.tipo).lower() or "suceso sin nombre"
    partes.append(f"— {suceso}" if partes else suceso.capitalize())
    entidad = c.entidad()
    if entidad:
        partes.append(f"({entidad})")
    lugar = c.en_lugar()
    texto = " ".join(partes) + lugar + "."
    return texto[0].upper() + texto[1:] if texto else texto


# ------------------------------------------------------------------ el motor
class Narrador:
    """Narra eventos resolviendo los nombres en tandas, no de uno en uno."""

    def __init__(self, conn: sqlite3.Connection, export_id: int) -> None:
        self.conn = conn
        self.export_id = export_id
        self.nombres: dict[str, dict[int, str]] = {
            "hf": {}, "sitio": {}, "entidad": {}, "artefacto": {},
            "estructura": {}, "region": {},
        }

    # --- resolución de nombres
    def preparar(self, filas: Iterable[dict]) -> None:
        pendientes = {clave: set() for clave in self.nombres}
        for fila in filas:
            datos = _cargar(fila)
            for papel, tabla in (("hf", "hf"), ("otro", "hf"), ("sitio", "sitio"),
                                 ("entidad", "entidad"), ("atacante", "entidad"),
                                 ("defensor", "entidad"), ("artefacto", "artefacto"),
                                 ("estructura", "estructura"), ("region", "region")):
                ident = Contexto(fila, datos, self.nombres)._id(papel)
                if ident is not None:
                    pendientes[tabla].add(ident)
            # Las figuras aparecen con muchos nombres distintos de campo.
            for clave, valor in datos.items():
                if clave.endswith("hfid") or clave in ("histfig", "hist_figure_id",
                                                       "hist_fig_id", "unit_id"):
                    try:
                        pendientes["hf"].add(int(str(valor).strip()))
                    except (TypeError, ValueError):
                        pass

        consultas = {
            "hf": ("historical_figures", "hf_id"),
            "sitio": ("sites", "site_id"),
            "entidad": ("entities", "entity_id"),
            "artefacto": ("artifacts", "artifact_id"),
            "estructura": ("site_structures", "structure_id"),
            "region": ("regions", "region_id"),
        }
        for tabla, ids in pendientes.items():
            faltan = [i for i in ids if i not in self.nombres[tabla]]
            if not faltan:
                continue
            nombre_tabla, columna = consultas[tabla]
            for trozo in _trozos(faltan, 400):
                marcas = ",".join("?" * len(trozo))
                sql = (f"SELECT {columna} AS id, name FROM {nombre_tabla} "
                       f"WHERE export_id = ? AND {columna} IN ({marcas})")
                try:
                    for r in self.conn.execute(sql, (self.export_id, *trozo)):
                        if r["name"]:
                            self.nombres[tabla][r["id"]] = r["name"]
                except sqlite3.Error:
                    continue

    def frase(self, fila: dict) -> str:
        datos = _cargar(fila)
        c = Contexto(fila, datos, self.nombres)
        plantilla = PLANTILLAS.get(c.tipo)
        try:
            texto = plantilla(c) if plantilla else generica(c)
        except Exception:  # pragma: no cover - una frase nunca tumba una ficha
            texto = generica(c)
        texto = " ".join(texto.split())
        return texto

    def narrar(self, filas: list[dict]) -> list[str]:
        self.preparar(filas)
        return [self.frase(f) for f in filas]


def _cargar(fila: dict) -> dict:
    crudo = fila.get("data_json")
    if isinstance(crudo, dict):
        return crudo
    if not crudo:
        return {}
    try:
        datos = json.loads(crudo)
        return datos if isinstance(datos, dict) else {}
    except (ValueError, TypeError):
        return {}


def _trozos(items: list, tamano: int):
    for i in range(0, len(items), tamano):
        yield items[i:i + tamano]


def cobertura() -> dict:
    """Cuántos tipos de evento sabemos narrar. Para la autocomprobación."""
    return {"con_plantilla": len(PLANTILLAS),
            "terminos": sum(len(t) for t in D.TABLAS.values())}
