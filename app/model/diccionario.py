"""Diccionario de términos de Dwarf Fortress al castellano.

Regla estricta: **lo que no esté aquí se muestra tal cual**. Nunca se inventa
una traducción ni se oculta un dato por no saber cómo llamarlo. Si aparece un
término desconocido, se limpia (guiones bajos por espacios, primera letra en
mayúscula) y se enseña, que es mejor que esconderlo.

Las frases están escritas a propósito sin género: el XML no dice si una figura
es «él» o «ella», así que en vez de arriesgarse se usan giros que valen para
cualquiera («murió por un disparo» en lugar de «fue disparada»).
"""

from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------- utilidades
def limpiar(termino: Optional[str]) -> str:
    """Un término desconocido, al menos legible: 'DARK_FORTRESS' -> 'Dark fortress'.

    Los códigos internos de DF van en mayúsculas y con guiones bajos. Se bajan a
    minúscula (si no, la frase se lee a gritos) pero no se traduce nada: lo que
    no está en el diccionario se enseña tal cual, solo que peinado.
    """
    if termino is None:
        return ""
    texto = str(termino).replace("_", " ").strip()
    if not texto:
        return ""
    letras = [c for c in texto if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        texto = texto.lower()
    return texto[0].upper() + texto[1:]


def traducir(termino: Optional[str], tabla: dict) -> str:
    """Busca el término en una tabla; si no está, lo devuelve limpio."""
    if termino is None:
        return ""
    clave = str(termino).strip()
    if clave in tabla:
        return tabla[clave]
    bajo = clave.lower()
    if bajo in tabla:
        return tabla[bajo]
    alto = clave.upper()
    if alto in tabla:
        return tabla[alto]
    return limpiar(clave)


# ------------------------------------------------------------ tipos de sitio
SITIOS = {
    "town": "ciudad",
    "city": "ciudad",
    "hamlet": "aldea",
    "village": "aldea",
    "fortress": "fortaleza",
    "fort": "fuerte",
    "dark fortress": "fortaleza oscura",
    "dark pits": "pozos oscuros",
    "forest retreat": "retiro forestal",
    "hillocks": "colinas habitadas",
    "mountain halls": "salones de la montaña",
    "cave": "cueva",
    "lair": "guarida",
    "shrine": "santuario",
    "labyrinth": "laberinto",
    "tomb": "tumba",
    "tower": "torre",
    "vault": "bóveda",
    "camp": "campamento",
    "castle": "castillo",
    "monastery": "monasterio",
    "important location": "lugar señalado",
    "mysterious palace": "palacio misterioso",
    "mysterious dungeon": "mazmorra misteriosa",
    "mysterious lair": "guarida misteriosa",
    "mysterious temple": "templo misterioso",
}

# --------------------------------------------------------- tipos de región
REGIONES = {
    "Ocean": "océano",
    "Lake": "lago",
    "Mountains": "montañas",
    "Hills": "colinas",
    "Forest": "bosque",
    "Jungle": "selva",
    "Grassland": "pradera",
    "Savanna": "sabana",
    "Steppe": "estepa",
    "Shrubland": "matorral",
    "Desert": "desierto",
    "Badland": "yermo",
    "Wetland": "humedal",
    "Marsh": "marisma",
    "Swamp": "pantano",
    "Tundra": "tundra",
    "Glacier": "glaciar",
    "cavern": "caverna",
    "underworld": "inframundo",
    "magma": "mar de magma",
}

EVILNESS = {
    "good": "bendita",
    "neutral": "neutral",
    "evil": "maldita",
}

# ------------------------------------------------------------ estructuras
ESTRUCTURAS = {
    "temple": "templo",
    "keep": "torreón",
    "tomb": "tumba",
    "dungeon": "mazmorra",
    "market": "mercado",
    "tower": "torre",
    "inn tavern": "taberna",
    "inn_tavern": "taberna",
    "library": "biblioteca",
    "guildhall": "casa gremial",
    "mead hall": "hidromielería",
    "underworld spire": "aguja del inframundo",
    "counting house": "casa de cuentas",
    "hospital": "hospital",
}

# ---------------------------------------------------------- tipos de entidad
ENTIDADES = {
    "civilization": "civilización",
    "sitegovernment": "gobierno del sitio",
    "site government": "gobierno del sitio",
    "religion": "religión",
    "outcast": "grupo de proscritos",
    "nomadicgroup": "grupo nómada",
    "nomadic group": "grupo nómada",
    "migratinggroup": "grupo migratorio",
    "performancetroupe": "compañía de artistas",
    "performance troupe": "compañía de artistas",
    "merchantcompany": "compañía mercante",
    "merchant company": "compañía mercante",
    "guild": "gremio",
    "military unit": "unidad militar",
    "militaryunit": "unidad militar",
}

# ------------------------------------------------------------- causas de muerte
# Escritas como complemento de «murió ...», sin género.
MUERTES = {
    "OLD_AGE": "de vejez",
    "STARVED": "de hambre",
    "THIRST": "de sed",
    "DROWNED": "ahogándose",
    "BLED": "desangrándose",
    "SUFFOCATED": "por asfixia",
    "INFECTION": "por una infección",
    "STRUCK": "por un golpe",
    "SHOT": "por un disparo",
    "MURDERED": "asesinada a traición",
    "SLAUGHTER": "en una matanza",
    "SCARE": "de miedo",
    "SCARED_TO_DEATH": "de miedo",
    "COLD": "por el frío",
    "HEAT": "por el calor",
    "SPIKE": "en una trampa de pinchos",
    "TRAP": "en una trampa",
    "CAVEIN": "en un derrumbe",
    "DRAIN_BLOOD": "desangrada por un vampiro",
    "COLLISION": "al chocar contra un obstáculo",
    "FALLING_OBJECT": "aplastada por algo que cayó",
    "FLYING_OBJECT": "por un objeto lanzado",
    "CRUSHED_BRIDGE": "aplastada por un puente",
    "DRAGONFIRE": "por el fuego de dragón",
    "DRAGONS_FIRE": "por el fuego de dragón",
    "BURNED": "por el fuego",
    "FIRE": "por el fuego",
    "MELT": "derretida",
    "POISON": "envenenada",
    "PUT_TO_REST": "por fin en paz",
    "QUIT": "de inanición al abandonarse la partida",
    "OBSTACLE": "al chocar contra un obstáculo",
    "EXECUTION_GENERIC": "ejecutada",
    "EXECUTION_BEHEADED": "decapitada en una ejecución",
    "EXECUTION_CRUCIFIED": "crucificada",
    "EXECUTION_BURIED_ALIVE": "enterrada viva",
    "EXECUTION_DROWNED": "ahogada en una ejecución",
    "EXECUTION_BURNED_ALIVE": "quemada viva",
    "EXECUTION_FED_TO_BEASTS": "arrojada a las bestias",
    "EXECUTION_HACKED_TO_PIECES": "descuartizada",
    "EXECUTION_CAGE": "encerrada en una jaula hasta morir",
    "VANISH": "desapareciendo sin dejar rastro",
    "NONE": "",
}

# ----------------------------------------------- vínculos entre figuras
VINCULOS_HF = {
    "spouse": "cónyuge",
    "mother": "madre",
    "father": "padre",
    "child": "hijo o hija",
    "sibling": "hermano o hermana",
    "lover": "amante",
    "friend": "amistad",
    "former spouse": "antiguo cónyuge",
    "deity": "deidad",
    "apprentice": "aprendiz",
    "master": "maestro",
    "former apprentice": "antiguo aprendiz",
    "former master": "antiguo maestro",
    "companion": "compañero de viaje",
    "prisoner": "prisionero",
    "former prisoner": "antiguo prisionero",
    "pet owner": "dueño",
    "bonded": "vínculo de sangre",
}

# ----------------------------------------------- vínculos con entidades
VINCULOS_ENTIDAD = {
    "member": "miembro",
    "former member": "antiguo miembro",
    "position": "cargo",
    "former position": "antiguo cargo",
    "prisoner": "prisionero",
    "former prisoner": "antiguo prisionero",
    "slave": "esclavo",
    "former slave": "antiguo esclavo",
    "enemy": "enemigo",
    "criminal": "criminal",
    "squad": "escuadra",
    "former squad": "antigua escuadra",
    "ruler": "gobernante",
    "worship": "fiel",
}

# ----------------------------------------------- vínculos con sitios
VINCULOS_SITIO = {
    "seat of power": "sede de su poder",
    "home site building": "vivienda",
    "home structure": "vivienda",
    "home site underground": "refugio subterráneo",
    "home site abstract building": "residencia",
    "hangout": "refugio",
    "lair": "guarida",
    "occupation": "puesto de trabajo",
    "prison": "prisión",
}

# ------------------------------------------------------ estados de una figura
ESTADOS_HF = {
    "settled": "se asentó",
    "wandering": "se echó al camino",
    "refugee": "huyó como refugiada",
    "scouting": "salió de exploración",
    "snatcher": "se dedicó a robar niños",
    "thief": "se dedicó al robo",
    "visiting": "se fue de visita",
    "hunting": "salió de caza",
}

# --------------------------------------------------------------- profesiones
PROFESIONES = {
    "MINER": "minería",
    "WOODWORKER": "carpintería",
    "CARPENTER": "carpintería",
    "STONEWORKER": "cantería",
    "MASON": "albañilería",
    "METALSMITH": "herrería",
    "WEAPONSMITH": "forja de armas",
    "ARMORER": "forja de armaduras",
    "BLACKSMITH": "herrería",
    "JEWELER": "joyería",
    "CRAFTSMAN": "artesanía",
    "FARMER": "labranza",
    "BREWER": "elaboración de bebidas",
    "COOK": "cocina",
    "FISHERMAN": "pesca",
    "HUNTER": "caza",
    "TRAPPER": "trampería",
    "RANGER": "montaraz",
    "MERCHANT": "comercio",
    "TRADER": "comercio",
    "DOCTOR": "medicina",
    "SURGEON": "cirugía",
    "SCHOLAR": "estudio",
    "PHILOSOPHER": "filosofía",
    "ASTRONOMER": "astronomía",
    "MATHEMATICIAN": "matemáticas",
    "HISTORIAN": "historia",
    "POET": "poesía",
    "BARD": "juglaría",
    "DANCER": "danza",
    "MUSICIAN": "música",
    "SOLDIER": "milicia",
    "AXEMAN": "hacha",
    "SWORDSMAN": "espada",
    "MACEMAN": "maza",
    "HAMMERMAN": "martillo",
    "SPEARMAN": "lanza",
    "PIKEMAN": "pica",
    "CROSSBOWMAN": "ballesta",
    "BOWMAN": "arco",
    "LASHER": "látigo",
    "WRESTLER": "lucha",
    "MERCENARY": "mercenaria",
    "MONSTER_SLAYER": "caza de monstruos",
    "PERFORMER": "espectáculo",
    "BEAST_HUNTER": "caza de bestias",
    "SCOUT": "exploración",
    "THIEF": "robo",
    "CRIMINAL": "crimen",
    "STANDARD": "sin oficio conocido",
}

# ------------------------------------------------------------------ cargos
CARGOS = {
    "MONARCH": "monarca",
    "KING": "rey o reina",
    "QUEEN": "reina",
    "PRINCE": "príncipe o princesa",
    "LORD": "señor o señora",
    "LADY": "señora",
    "DUKE": "duque o duquesa",
    "COUNT": "conde o condesa",
    "BARON": "barón o baronesa",
    "MAYOR": "alcalde o alcaldesa",
    "CHIEF": "jefe o jefa",
    "WAR_CHIEF": "jefe de guerra",
    "WARLORD": "señor de la guerra",
    "GENERAL": "general",
    "LIEUTENANT": "teniente",
    "CAPTAIN": "capitán o capitana",
    "MILITIA_COMMANDER": "comandante de la milicia",
    "MILITIA_CAPTAIN": "capitán de la milicia",
    "CAPTAIN_OF_THE_GUARD": "capitán de la guardia",
    "SHERIFF": "alguacil",
    "HAMMERER": "verdugo",
    "LAW_GIVER": "legislador",
    "EXPEDITION_LEADER": "líder de la expedición",
    "OUTPOST_LIAISON": "enlace del puesto avanzado",
    "DIPLOMAT": "diplomático",
    "MERCHANT_BARON": "barón mercante",
    "MERCHANT_PRINCE": "príncipe mercante",
    "GUILD_REPRESENTATIVE": "representante del gremio",
    "MANAGER": "administrador",
    "BOOKKEEPER": "contable",
    "BROKER": "corredor de comercio",
    "CHIEF_MEDICAL_DWARF": "médico jefe",
    "PRIEST": "sacerdote",
    "HIGH_PRIEST": "sumo sacerdote",
    "DRUID": "druida",
    "CHAMPION": "campeón o campeona",
    "MASTER_ASSASSIN": "maestro de asesinos",
    "CRIMINAL_UNDERWORLD_LEADER": "capo del hampa",
    "FORCED_ADMINISTRATOR": "administrador impuesto",
    "GENERAL_OF_THE_ARMIES": "general de los ejércitos",
    "MASTER_OF_THE_HUNT": "montero mayor",
    "PERFORMANCE_TROUPE_LEADER": "director de la compañía",
    "SCHOLAR": "erudito",
    "MESSENGER": "mensajero",
}

# ------------------------------------------------------------- habilidades
HABILIDADES = {
    "AXE": "hacha",
    "SWORD": "espada",
    "MACE": "maza",
    "HAMMER": "martillo",
    "SPEAR": "lanza",
    "PIKE": "pica",
    "CROSSBOW": "ballesta",
    "BOW": "arco",
    "WHIP": "látigo",
    "KNIFE": "cuchillo",
    "DAGGER": "daga",
    "SHIELD": "escudo",
    "ARMOR_USE": "uso de armadura",
    "DODGING": "esquiva",
    "MELEE_COMBAT": "combate cuerpo a cuerpo",
    "RANGED_COMBAT": "combate a distancia",
    "WRESTLING": "lucha",
    "BITE": "mordisco",
    "GRASP_STRIKE": "puñetazo",
    "STANCE_STRIKE": "patada",
    "MINING": "minería",
    "MASONRY": "albañilería",
    "CARPENTRY": "carpintería",
    "SMITHING": "herrería",
    "PERSUASION": "persuasión",
    "INTIMIDATION": "intimidación",
    "NEGOTIATION": "negociación",
    "LYING": "mentira",
    "INTRIGUE": "intriga",
    "POETRY": "poesía",
    "MUSIC": "música",
    "DANCE": "danza",
    "WRITING": "escritura",
    "READING": "lectura",
    "SPEAKING": "oratoria",
    "LEADERSHIP": "liderazgo",
    "TEACHING": "enseñanza",
    "ORGANIZATION": "organización",
    "CONCENTRATION": "concentración",
    "DISCIPLINE": "disciplina",
    "TRACKING": "rastreo",
    "SWIMMING": "natación",
    "CLIMBING": "escalada",
}

# ---------------------------------------------------------------- esferas
ESFERAS = {
    "war": "la guerra",
    "death": "la muerte",
    "fortresses": "las fortalezas",
    "wealth": "la riqueza",
    "nature": "la naturaleza",
    "fire": "el fuego",
    "water": "el agua",
    "earth": "la tierra",
    "wind": "el viento",
    "sun": "el sol",
    "moon": "la luna",
    "night": "la noche",
    "darkness": "la oscuridad",
    "light": "la luz",
    "love": "el amor",
    "hate": "el odio",
    "fate": "el destino",
    "luck": "la suerte",
    "trickery": "el engaño",
    "wisdom": "la sabiduría",
    "craft": "la artesanía",
    "healing": "la curación",
    "disease": "la enfermedad",
    "murder": "el asesinato",
    "revenge": "la venganza",
    "silence": "el silencio",
    "storms": "las tormentas",
    "blight": "la plaga",
    "birth": "el nacimiento",
    "children": "la infancia",
    "family": "la familia",
    "jewels": "las joyas",
    "metals": "los metales",
    "mountains": "las montañas",
    "forests": "los bosques",
    "rivers": "los ríos",
    "oceans": "los océanos",
    "seasons": "las estaciones",
    "boundaries": "las fronteras",
    "chaos": "el caos",
    "order": "el orden",
    "justice": "la justicia",
    "lies": "la mentira",
    "dreams": "los sueños",
    "nightmares": "las pesadillas",
    "victory": "la victoria",
    "valor": "el valor",
    "duty": "el deber",
    "sacrifice": "el sacrificio",
    "suicide": "el suicidio",
    "torture": "la tortura",
    "youth": "la juventud",
    "wgroup": "los grupos",
}

# --------------------------------------------------------- objetivos vitales
OBJETIVOS = {
    "IMMORTALITY": "alcanzar la inmortalidad",
    "MASTER_A_SKILL": "dominar un oficio hasta la perfección",
    "RULE_THE_WORLD": "gobernar el mundo",
    "CREATE_A_GREAT_WORK_OF_ART": "crear una gran obra de arte",
    "CRAFT_A_MASTERWORK": "forjar una obra maestra",
    "BRING_PEACE_TO_THE_WORLD": "traer la paz al mundo",
    "BE_REMEMBERED": "ser recordada para siempre",
    "MAKE_A_GREAT_DISCOVERY": "hacer un gran descubrimiento",
    "FALL_IN_LOVE": "encontrar el amor",
    "START_A_FAMILY": "formar una familia",
    "BECOME_A_LEGENDARY_WARRIOR": "convertirse en guerrera legendaria",
    "SEE_THE_GREAT_NATURAL_SITES": "ver las grandes maravillas naturales",
    "MAINTAIN_ENTITY_STATUS": "mantener el orden establecido",
    "ATTAIN_RANK_IN_SOCIETY": "escalar en la sociedad",
    "STAY_ALIVE": "seguir con vida",
    "BATHE_WORLD_IN_CHAOS": "sumir el mundo en el caos",
}

# ------------------------------------------------------------ conocimientos
SECRETOS = {
    "SECRET_OF_LIFE_AND_DEATH": "el secreto de la vida y la muerte",
    "SECRET_OF_NATURE": "los secretos de la naturaleza",
    "SECRET_OF_ETERNAL_LIFE": "el secreto de la vida eterna",
}

# -------------------------------------------------- clase de figura histórica
TIPOS_FIGURA = {
    "standard": "gente corriente",
    "megabeast": "bestia legendaria",
    "semimegabeast": "bestia mayor",
    "titan": "titán",
    "night creature": "criatura de la noche",
    "night_creature": "criatura de la noche",
    "demon": "demonio",
    "god": "dios",
    "deity": "deidad",
    "force": "fuerza primordial",
    "vampire": "vampiro",
    "werebeast": "hombre bestia",
    "necromancer": "nigromante",
    "ghost": "fantasma",
    "zombie": "muerto viviente",
}

# ------------------------------------------------------ tipos de construcción
CONSTRUCCIONES = {
    "road": "calzada",
    "bridge": "puente",
    "tunnel": "túnel",
    "wall": "muralla",
    "aqueduct": "acueducto",
}

# ----------------------------------------------------- colecciones de eventos
COLECCIONES = {
    "war": "guerra",
    "battle": "batalla",
    "duel": "duelo",
    "raid": "saqueo",
    "site conquered": "conquista de un sitio",
    "abduction": "secuestro",
    "theft": "robo",
    "beast attack": "ataque de una bestia",
    "insurrection": "levantamiento",
    "purge": "purga",
    "persecution": "persecución",
    "journey": "viaje",
    "occasion": "celebración",
    "ceremony": "ceremonia",
    "competition": "competición",
    "performance": "actuación",
    "procession": "procesión",
    "entity overthrown": "derrocamiento",
    "coup": "golpe de estado",
}

# Todas las tablas juntas, para el interruptor de «ver en bruto» y las pruebas.
TABLAS = {
    "sitios": SITIOS,
    "regiones": REGIONES,
    "estructuras": ESTRUCTURAS,
    "entidades": ENTIDADES,
    "muertes": MUERTES,
    "vinculos_hf": VINCULOS_HF,
    "vinculos_entidad": VINCULOS_ENTIDAD,
    "vinculos_sitio": VINCULOS_SITIO,
    "estados_hf": ESTADOS_HF,
    "profesiones": PROFESIONES,
    "habilidades": HABILIDADES,
    "esferas": ESFERAS,
    "objetivos": OBJETIVOS,
    "secretos": SECRETOS,
    "tipos_figura": TIPOS_FIGURA,
    "construcciones": CONSTRUCCIONES,
    "colecciones": COLECCIONES,
    "cargos": CARGOS,
    "evilness": EVILNESS,
}


# ------------------------------------------------------------- atajos cómodos
def sitio(t):        return traducir(t, SITIOS)          # noqa: E704
def region(t):       return traducir(t, REGIONES)        # noqa: E704
def estructura(t):   return traducir(t, ESTRUCTURAS)     # noqa: E704
def entidad(t):      return traducir(t, ENTIDADES)       # noqa: E704
def muerte(t):       return traducir(t, MUERTES)         # noqa: E704
def vinculo_hf(t):   return traducir(t, VINCULOS_HF)     # noqa: E704
def vinculo_ent(t):  return traducir(t, VINCULOS_ENTIDAD)  # noqa: E704
def vinculo_sitio(t): return traducir(t, VINCULOS_SITIO)  # noqa: E704
def profesion(t):    return traducir(t, PROFESIONES)     # noqa: E704
def habilidad(t):    return traducir(t, HABILIDADES)     # noqa: E704
def esfera(t):       return traducir(t, ESFERAS)         # noqa: E704
def objetivo(t):     return traducir(t, OBJETIVOS)       # noqa: E704
def secreto(t):      return traducir(t, SECRETOS)        # noqa: E704
def tipo_figura(t):  return traducir(t, TIPOS_FIGURA)    # noqa: E704
def construccion(t): return traducir(t, CONSTRUCCIONES)  # noqa: E704
def coleccion(t):    return traducir(t, COLECCIONES)     # noqa: E704
def cargo(t):        return traducir(t, CARGOS)          # noqa: E704
