"""Genera un export de legends de mentira para probar la aplicacion.

No necesitas usarlo: sirve para comprobar que el parser funciona sin tener a
mano tus ficheros de 45 MB. Reproduce a proposito las trampas del formato real:
codificacion CP437, bytes de control C0 dentro de los nombres, etiquetas <n> en
lugar de <name>, y datos repartidos entre el fichero principal y el _plus.

    python tools/make_sample_export.py data/imports
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Bytes de control que DF mete dentro de los nombres. En CP437 el 0x0F es el
# simbolo del sol (objetos de calidad) y el 0x0E una nota musical.
SOL = "\x0f"
NOTA = "\x0e"
FLECHA = "\x1a"


def _sites(world_size: int, extra_fort: bool):
    sitios = [
        (0, "dark fortress", "ustuthlolor", 9, 4),
        (1, "fortress", "kolluslan", 22, 17),
        (2, "hillocks", "bomrekgusil", 24, 19),
        (3, "town", "iteb" + SOL + "lokum", 31, 26),
        (4, "forest retreat", "loralethes", 12, 30),
        (5, "cave", "ngokangdakost", 5, 22),
        (6, "tower", "kadolnicot", 28, 8),
        (7, "lair", "shorastnokzon", 17, 35),
        (8, "vault", "asmelanam", 2, 2),
        (9, "hamlet", "gusilkir" + NOTA + "am", 33, 24),
        (10, "labyrinth", "onolzasit", 36, 12),
    ]
    if extra_fort:
        sitios.append((11, "fortress", "bronzemurder", 21, 20))
    return [s for s in sitios if s[3] < world_size and s[4] < world_size]


ENTIDADES = [
    (0, "The Bronze Confederacy", "civilization", "DWARF", [20, 21, 22]),
    (1, "The Vile Empire of Torment", "civilization", "GOBLIN", [23]),
    (2, "The Green Circle", "civilization", "ELF", [24]),
    (3, "The Order of Silver", "religion", "", []),
    (20, "Kolluslan Government", "sitegovernment", "DWARF", []),
    (21, "Bomrekgusil Government", "sitegovernment", "DWARF", []),
    (22, "Bronzemurder Government", "sitegovernment", "DWARF", []),
    (23, "Ustuthlolor Government", "sitegovernment", "GOBLIN", []),
    (24, "Loralethes Government", "sitegovernment", "ELF", []),
]

RAZAS = ["DWARF", "GOBLIN", "ELF", "HUMAN", "DRAGON", "TITAN"]


def build(prefix: str, year: int, extra_fort: bool, seed: int) -> tuple[str, str]:
    rnd = random.Random(seed)
    world_size = 40
    sitios = _sites(world_size, extra_fort)

    # ---------------------------------------------------------- principal
    m = ['<?xml version="1.0" encoding=\'CP437\'?>', "<df_world>",
         "<name>ozorothsanreg</name>",
         "<altname>The Universe of Legend" + SOL + "s</altname>",
         "<regions>"]
    for i, tipo in enumerate(["Forest", "Mountains", "Desert", "Tundra"]):
        m.append(f"<region><id>{i}</id><name>the region of {tipo.lower()}</name><type>{tipo}</type></region>")
    m.append("</regions>")

    m.append("<sites>")
    for sid, tipo, nombre, x, y in sitios:
        m.append(f"<site><id>{sid}</id><type>{tipo}</type><n>{nombre}</n>"
                 f"<coords>{x},{y}</coords><rectangle>{x},{y}:{x+1},{y+1}</rectangle>"
                 f"<structures><structure><local_id>0</local_id><type>keep</type>"
                 f"<name>the keep of {nombre}</name></structure></structures></site>")
    m.append("</sites>")

    m.append("<artifacts>")
    artefactos = [(0, "Nishtulomith", 1, 100), (1, "Ducimatis" + SOL, 3, 101),
                  (2, "Ridethmomuz", 2, 102)]
    if extra_fort:
        artefactos.append((3, "Zasitethkos" + FLECHA, 11, 103))
    for aid, nombre, sid, hf in artefactos:
        m.append(f"<artifact><id>{aid}</id><name>{nombre}</name>"
                 f"<item><name_string>a steel warhammer named {nombre}</name_string></item>"
                 f"<site_id>{sid}</site_id><holder_hfid>{hf}</holder_hfid></artifact>")
    m.append("</artifacts>")

    m.append("<historical_figures>")
    figuras = []
    for i in range(100, 130):
        raza = RAZAS[i % len(RAZAS)]
        muerto = (i % 3 == 0) and i < 120
        death = (150 + i % 40) if muerto else -1
        if extra_fort and i in (105, 111):
            death = year - 1
        figuras.append((i, raza, death))
        nombre = f"figura{i} Nombre{'é' if i % 5 == 0 else ''}"
        m.append(
            f"<historical_figure><id>{i}</id><name>{nombre}</name><race>{raza}</race>"
            f"<caste>{'FEMALE' if i % 2 else 'MALE'}</caste>"
            f"<birth_year>{60 + i % 50}</birth_year><birth_seconds>-1</birth_seconds>"
            f"<death_year>{death}</death_year><death_seconds>-1</death_seconds>"
            + f"<associated_type>{'megabeast' if i % 7 == 0 else 'standard'}</associated_type>"
            + f"<entity_link><entity_id>{i % 3}</entity_id>"
              "<link_type>member</link_type><link_strength>100</link_strength></entity_link>"
            + f"<hf_skill><skill>AXE</skill><total_ip>{rnd.randint(100, 9000)}</total_ip></hf_skill>"
            + "<goal>MAINTAIN_ENTITY_STATUS</goal>"
            + "</historical_figure>"
        )
    m.append("</historical_figures>")

    m.append("<historical_events>")
    eid = 0
    eventos = []

    def ev(texto: str) -> None:
        nonlocal eid
        eventos.append(f"<historical_event><id>{eid}</id>{texto}</historical_event>")
        eid += 1

    ev("<year>50</year><seconds72>0</seconds72><type>created site</type>"
       "<civ_id>0</civ_id><site_civ_id>20</site_civ_id><site_id>1</site_id>")
    ev("<year>62</year><seconds72>0</seconds72><type>created site</type>"
       "<civ_id>0</civ_id><site_civ_id>21</site_civ_id><site_id>2</site_id>")
    ev("<year>45</year><seconds72>0</seconds72><type>created site</type>"
       "<civ_id>1</civ_id><site_civ_id>23</site_civ_id><site_id>0</site_id>")
    ev("<year>70</year><seconds72>0</seconds72><type>created site</type>"
       "<civ_id>2</civ_id><site_civ_id>24</site_civ_id><site_id>4</site_id>")
    ev("<year>120</year><seconds72>10</seconds72><type>site taken over</type>"
       "<attacker_civ_id>1</attacker_civ_id><defender_civ_id>0</defender_civ_id>"
       "<site_civ_id>21</site_civ_id><new_site_civ_id>23</new_site_civ_id><site_id>2</site_id>")
    ev("<year>145</year><seconds72>5</seconds72><type>destroyed site</type>"
       "<attacker_civ_id>1</attacker_civ_id><defender_civ_id>2</defender_civ_id>"
       "<site_civ_id>24</site_civ_id><site_id>4</site_id>")
    ev("<year>150</year><seconds72>0</seconds72><type>hf destroyed site</type>"
       "<attacker_hfid>121</attacker_hfid><site_id>5</site_id><defender_civ_id>0</defender_civ_id>")
    for i, (hf, raza, death) in enumerate(figuras):
        if death != -1:
            ev(f"<year>{death}</year><seconds72>{i}</seconds72><type>hf died</type>"
               f"<hfid>{hf}</hfid><slayer_hfid>{121 if i % 2 else 126}</slayer_hfid>"
               f"<cause>STRUCK</cause><site_id>{i % 5}</site_id>")
    for aid, nombre, sid, hf in artefactos:
        ev(f"<year>{90 + aid * 7}</year><seconds72>0</seconds72><type>created artifact</type>"
           f"<artifact_id>{aid}</artifact_id><hfid>{hf}</hfid><site_id>{sid}</site_id>")
    for anyo in range(100, year, 6):
        ev(f"<year>{anyo}</year><seconds72>0</seconds72><type>merchant</type>"
           f"<site_id>1</site_id><trader_entity_id>0</trader_entity_id><depot_entity_id>20</depot_entity_id>")
    if extra_fort:
        ev(f"<year>{year - 4}</year><seconds72>0</seconds72><type>created site</type>"
           f"<civ_id>0</civ_id><site_civ_id>22</site_civ_id><site_id>11</site_id>")
        ev(f"<year>{year - 1}</year><seconds72>0</seconds72><type>attacked site</type>"
           f"<attacker_civ_id>1</attacker_civ_id><defender_civ_id>0</defender_civ_id><site_id>11</site_id>")
    m.extend(eventos)
    m.append("</historical_events>")

    m.append("<historical_event_collections>")
    m.append("<historical_event_collection><id>0</id><start_year>110</start_year>"
             "<end_year>-1</end_year><type>war</type><name>the War of Rust</name>"
             "<attacking_enid>1</attacking_enid><defending_enid>0</defending_enid>"
             "<event>4</event></historical_event_collection>")
    m.append("</historical_event_collections>")

    m.append("<entities>")
    for eidx, nombre, tipo, raza, hijos in ENTIDADES:
        m.append(f"<entity><id>{eidx}</id><name>{nombre}</name></entity>")
    m.append("</entities>")
    m.append("</df_world>")

    # --------------------------------------------------------------- plus
    p = ['<?xml version="1.0" encoding=\'CP437\'?>', "<df_world>",
         "<name>ozorothsanreg</name>", "<sites>"]
    duenyos = {0: 23, 1: 20, 2: 23, 3: None, 4: 24, 5: None, 6: None,
               7: None, 8: None, 9: 20, 10: None, 11: 22}
    for sid, tipo, nombre, x, y in sitios:
        civ = duenyos.get(sid)
        extra = f"<civ_id>{civ}</civ_id><cur_owner_id>{civ}</cur_owner_id>" if civ else ""
        p.append(f"<site><id>{sid}</id><name>{nombre}</name><type>{tipo}</type>"
                 f"<coords>{x},{y}</coords>{extra}</site>")
    p.append("</sites>")

    p.append("<entities>")
    for eidx, nombre, tipo, raza, hijos in ENTIDADES:
        hijos_xml = "".join(f"<child>{c}</child>" for c in hijos)
        raza_xml = f"<race>{raza}</race>" if raza else ""
        p.append(f"<entity><id>{eidx}</id><n>{nombre}</n><type>{tipo}</type>{raza_xml}{hijos_xml}"
                 f"<entity_position><id>0</id><name>rey</name></entity_position>"
                 f"<entity_position_assignment><id>0</id><position_id>0</position_id>"
                 f"<histfig>{100 + eidx}</histfig></entity_position_assignment></entity>")
    p.append("</entities>")

    p.append("<historical_figures>")
    for i in range(100, 130):
        extras = ""
        if i % 7 == 0:
            extras += "<interaction_knowledge>SECRET_OF_LIFE_AND_DEATH</interaction_knowledge>"
        if i % 11 == 0:
            extras += ("<intrigue_plot><type>corrupt</type><agreement_id>3</agreement_id>"
                       f"<parent_plot_hfid>{i - 1}</parent_plot_hfid></intrigue_plot>")
        p.append(f"<historical_figure><id>{i}</id><sphere>war</sphere>{extras}"
                 f"<site_link><link_type>seat of power</link_type><site_id>{i % 5}</site_id></site_link>"
                 f"</historical_figure>")
    p.append("</historical_figures>")
    p.append("<entity_populations><entity_population><id>0</id><race>DWARF</race>"
             "<count>420</count><civ_id>0</civ_id></entity_population></entity_populations>")
    p.append("</df_world>")

    return "\n".join(m), "\n".join(p)


def main() -> int:
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "data/imports")
    destino.mkdir(parents=True, exist_ok=True)

    for prefix, year, extra, seed in (
        ("sample1-00120-01-01", 120, False, 1),
        ("sample1-00160-07-24", 160, True, 2),
    ):
        principal, plus = build(prefix, year, extra, seed)
        (destino / f"{prefix}-legends.xml").write_bytes(principal.encode("cp437", errors="replace"))
        (destino / f"{prefix}-legends_plus.xml").write_bytes(plus.encode("cp437", errors="replace"))
        print(f"generado {prefix} (principal + plus)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
