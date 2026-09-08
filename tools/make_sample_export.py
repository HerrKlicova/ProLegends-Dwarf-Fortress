"""Genera exports de legends de mentira para probar la aplicacion.

No hace falta para el uso normal: sirve para comprobar que todo funciona sin
tener a mano tus ficheros de 45 MB, y para hacer pruebas de carga. Reproduce a
proposito las trampas del formato real: codificacion CP437, bytes de control C0
dentro de los nombres, etiquetas <n> en lugar de <name>, y datos repartidos
entre el fichero principal y el _plus.

Ejemplos:

    # dos exports de un mundo pequenyo, con fortaleza nueva en el segundo
    python tools/make_sample_export.py

    # un mundo distinto, más grande
    python tools/make_sample_export.py --mundo tegurxosal --token region4 --tam 129

    # una prueba de carga de unos 45 MB
    python tools/make_sample_export.py --mundo carga --token region9 --tam 257 \\
        --sitios 1800 --figuras 60000 --eventos 320000 --solo-uno
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

# Bytes de control que DF mete dentro de los nombres. En CP437 el 0x0F es el
# símbolo del sol de los objetos de calidad y el 0x0E una nota musical.
SOL, NOTA, FLECHA = "\x0f", "\x0e", "\x1a"

TIPOS_SITIO = ["town", "hamlet", "hillocks", "fortress", "dark fortress", "forest retreat",
               "cave", "tower", "lair", "vault", "labyrinth", "shrine", "camp", "tomb",
               "mountain halls", "monastery", "castle"]
RAZAS_CIV = ["DWARF", "GOBLIN", "ELF", "HUMAN", "KOBOLD"]
RAZAS_BESTIA = ["DRAGON", "ROC", "HYDRA", "TITAN", "MINOTAUR", "CYCLOPS"]
TIPOS_ASOC = ["standard", "megabeast", "semimegabeast", "titan", "night creature"]
HABILIDADES = ["AXE", "SWORD", "HAMMER", "MINING", "MASONRY", "PERSUASION", "POETRY",
               "ARMOR_USE", "DODGING", "MELEE_COMBAT"]
SILABAS = ["kol", "lus", "lan", "bom", "rek", "gus", "il", "ith", "mo", "muz", "zas", "et",
           "hkos", "ngo", "kang", "dak", "ost", "shor", "ast", "nok", "zon", "asm", "el",
           "anam", "ust", "uth", "lol", "or", "onol", "rig", "oth", "san"]


def palabra(rnd: random.Random, n: int = 3) -> str:
    return "".join(rnd.choice(SILABAS) for _ in range(n))


# --------------------------------------------------------------- geografia
# Un mundo con costas, relieve, biomas y rios, para poder probar el mapa sin
# tener a mano un export de verdad. Imita la forma en que DF reparte los datos:
# el fichero principal da el nombre y el tipo de cada region, y el _plus da las
# coordenadas de sus casillas.
TIPOS_REGION = ["Ocean", "Lake", "Mountains", "Hills", "Forest", "Jungle",
                "Grassland", "Steppe", "Desert", "Tundra", "Glacier", "Wetland"]


def _suave(t: float) -> float:
    return t * t * (3 - 2 * t)


def _ruido(rnd: random.Random, tam: int, celdas: int) -> list[list[float]]:
    """Ruido de valor interpolado: manchas suaves, sin dependencias."""
    rejilla = [[rnd.random() for _ in range(celdas + 2)] for _ in range(celdas + 2)]
    salida = [[0.0] * tam for _ in range(tam)]
    for y in range(tam):
        fy = y / max(1, tam) * celdas
        y0 = int(fy)
        ty = _suave(fy - y0)
        for x in range(tam):
            fx = x / max(1, tam) * celdas
            x0 = int(fx)
            tx = _suave(fx - x0)
            arriba = rejilla[y0][x0] * (1 - tx) + rejilla[y0][x0 + 1] * tx
            abajo = rejilla[y0 + 1][x0] * (1 - tx) + rejilla[y0 + 1][x0 + 1] * tx
            salida[y][x] = arriba * (1 - ty) + abajo * ty
    return salida


def _capas(rnd: random.Random, tam: int, capas=((3, 1.0), (7, 0.5), (15, 0.25))):
    total = [[0.0] * tam for _ in range(tam)]
    peso_total = sum(p for _, p in capas)
    for celdas, peso in capas:
        capa = _ruido(rnd, tam, celdas)
        for y in range(tam):
            fila, suya = total[y], capa[y]
            for x in range(tam):
                fila[x] += suya[x] * peso
    for y in range(tam):
        for x in range(tam):
            total[y][x] /= peso_total
    return total


def construir_geografia(rnd: random.Random, tam: int) -> dict:
    altura = _capas(rnd, tam)
    humedad = _capas(rnd, tam, ((2, 1.0), (5, 0.5)))

    # Empujar el mar hacia los bordes para que salgan continentes y no una
    # mancha que llega hasta el marco.
    centro = (tam - 1) / 2
    for y in range(tam):
        for x in range(tam):
            dx = abs(x - centro) / max(1.0, centro)
            dy = abs(y - centro) / max(1.0, centro)
            borde = max(dx, dy)
            altura[y][x] = altura[y][x] * (1.0 - 0.75 * borde ** 3)

    MAR = 0.42
    bioma = [["Ocean"] * tam for _ in range(tam)]
    for y in range(tam):
        # La latitud decide el frio: polos arriba y abajo.
        lat = abs(y - centro) / max(1.0, centro)
        for x in range(tam):
            h, w = altura[y][x], humedad[y][x]
            if h < MAR:
                bioma[y][x] = "Ocean"
            elif lat > 0.93:
                bioma[y][x] = "Glacier"
            elif lat > 0.82:
                bioma[y][x] = "Tundra"
            elif h > 0.70:
                bioma[y][x] = "Mountains"
            elif h > 0.60:
                bioma[y][x] = "Hills"
            elif h < MAR + 0.03 and w > 0.62:
                bioma[y][x] = "Wetland"
            elif w > 0.68:
                bioma[y][x] = "Jungle" if lat < 0.3 else "Forest"
            elif w > 0.50:
                bioma[y][x] = "Forest" if lat < 0.65 else "Grassland"
            elif w > 0.34:
                bioma[y][x] = "Grassland" if lat < 0.6 else "Steppe"
            else:
                bioma[y][x] = "Desert" if lat < 0.55 else "Steppe"

    # Lagos: agua sin salida al mar. Se buscan las bolsas de oceano que no
    # tocan el borde del mundo.
    visto = [[False] * tam for _ in range(tam)]
    for y0 in range(tam):
        for x0 in range(tam):
            if visto[y0][x0] or bioma[y0][x0] != "Ocean":
                continue
            bolsa, pila, toca_borde = [], [(x0, y0)], False
            visto[y0][x0] = True
            while pila:
                x, y = pila.pop()
                bolsa.append((x, y))
                if x in (0, tam - 1) or y in (0, tam - 1):
                    toca_borde = True
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < tam and 0 <= ny < tam and not visto[ny][nx] \
                            and bioma[ny][nx] == "Ocean":
                        visto[ny][nx] = True
                        pila.append((nx, ny))
            if not toca_borde and len(bolsa) <= max(24, tam):
                for x, y in bolsa:
                    bioma[y][x] = "Lake"

    tierra = {(x, y) for y in range(tam) for x in range(tam)
              if bioma[y][x] not in ("Ocean", "Lake")}

    # --- regiones: cada mancha contigua del mismo bioma es una region -----
    regiones, marca = [], [[False] * tam for _ in range(tam)]
    for y0 in range(tam):
        for x0 in range(tam):
            if marca[y0][x0]:
                continue
            tipo = bioma[y0][x0]
            casillas, pila = [], [(x0, y0)]
            marca[y0][x0] = True
            while pila:
                x, y = pila.pop()
                casillas.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < tam and 0 <= ny < tam and not marca[ny][nx] \
                            and bioma[ny][nx] == tipo:
                        marca[ny][nx] = True
                        pila.append((nx, ny))
            regiones.append({"id": len(regiones), "tipo": tipo,
                             "nombre": palabra(rnd, 2), "casillas": casillas})

    # --- rios: desde lo alto, siempre cuesta abajo, hasta el agua ---------
    rios = []
    cumbres = sorted(((altura[y][x], x, y) for x, y in tierra), reverse=True)
    for _, x, y in cumbres[: max(3, tam // 6)]:
        camino, visitadas = [], set()
        while True:
            camino.append((x, y))
            visitadas.add((x, y))
            if bioma[y][x] in ("Ocean", "Lake") or len(camino) > tam * 2:
                break
            # Cuesta abajo, sin volver sobre lo andado. Un rio se acaba cuando
            # deja de bajar: asi no salen espirales ni rectas infinitas.
            cerca = {(cx + dx, cy + dy) for cx, cy in camino[-5:]
                     for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            vecinas = [(altura[ny][nx] + (0.02 if (nx, ny) in cerca else 0.0), nx, ny)
                       for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                       if 0 <= nx < tam and 0 <= ny < tam and (nx, ny) not in visitadas]
            if not vecinas:
                break
            coste, nx, ny = min(vecinas)
            if altura[ny][nx] > altura[y][x]:
                break
            x, y = nx, ny
        if len(camino) >= 4:
            rios.append({"nombre": palabra(rnd, 2), "camino": camino})

    # --- picos con nombre -------------------------------------------------
    picos, puestos = [], []
    for h, x, y in cumbres:
        if bioma[y][x] != "Mountains":
            continue
        if any(abs(x - px) + abs(y - py) < tam // 5 for px, py in puestos):
            continue
        puestos.append((x, y))
        picos.append({"id": len(picos), "nombre": palabra(rnd, 2), "x": x, "y": y,
                      "altura": int(1000 + h * 4000),
                      "volcan": 1 if rnd.random() < 0.25 else 0})
        if len(picos) >= 4:
            break

    return {"tam": tam, "altura": altura, "bioma": bioma, "tierra": tierra,
            "regiones": regiones, "rios": rios, "picos": picos}


def construir_mundo(args):
    """Construye el mundo entero una sola vez, hasta el anyo final.

    Despues cada export es un recorte por anyo de este mismo mundo: asi los
    identificadores son estables entre exports y el export posterior contiene
    todo lo del anterior mas lo nuevo, que es como se comporta Dwarf Fortress.
    """
    rnd = random.Random(args.mundo)
    tam = args.tam
    anyo_final = args.anyo_final
    n_sitios = args.sitios + 1          # el último es la fortaleza del jugador
    n_civ = max(2, args.civilizaciones)

    entidades = []
    for i in range(n_civ):
        entidades.append({
            "id": i, "nombre": f"The {palabra(rnd, 2).title()} of {palabra(rnd, 2).title()}",
            "tipo": "civilization", "raza": RAZAS_CIV[i % len(RAZAS_CIV)], "hijos": [],
        })
    siguiente = n_civ
    gobiernos = []
    for s in range(n_sitios):
        civ = s % n_civ
        entidades.append({
            "id": siguiente, "nombre": f"{palabra(rnd, 2).title()} Government",
            "tipo": "sitegovernment", "raza": entidades[civ]["raza"], "hijos": [],
        })
        entidades[civ]["hijos"].append(siguiente)
        gobiernos.append((s, siguiente, civ))
        siguiente += 1

    geo = construir_geografia(rnd, tam)
    # Los asentamientos van en tierra firme, como en un mundo de verdad.
    libres = sorted(geo["tierra"])
    rnd.shuffle(libres)

    sitios, ocupadas = [], set()
    for s in range(n_sitios):
        while True:
            if libres:
                x, y = libres.pop()
            else:
                x, y = rnd.randrange(tam), rnd.randrange(tam)
            if (x, y) not in ocupadas:
                ocupadas.add((x, y)); break
        nombre = palabra(rnd, rnd.randint(2, 4))
        if s % 37 == 0:
            nombre += SOL
        elif s % 53 == 0:
            nombre += NOTA
        es_fortaleza = s == n_sitios - 1
        sitios.append({
            "id": s, "nombre": nombre, "x": x, "y": y,
            "tipo": "fortress" if es_fortaleza else rnd.choice(TIPOS_SITIO),
            "fundado": (anyo_final - 4) if es_fortaleza else 1 + (s * 3) % max(1, anyo_final - 8),
            "estructuras": [
                (k, rnd.choice(["keep", "temple", "market", "tomb", "tower"]))
                for k in range(rnd.randint(0, 4))
            ],
        })

    figuras = []
    for i in range(args.figuras):
        bestia = i % 41 == 0
        nacimiento = rnd.randrange(1, max(2, anyo_final))
        muere = rnd.random() < 0.55 and nacimiento + 1 <= anyo_final
        figuras.append({
            "id": i,
            "raza": rnd.choice(RAZAS_BESTIA) if bestia else RAZAS_CIV[i % len(RAZAS_CIV)],
            "nacimiento": nacimiento,
            "muerte": rnd.randrange(nacimiento + 1, anyo_final + 1) if muere else -1,
            "tipo": rnd.choice(TIPOS_ASOC[1:]) if bestia else "standard",
            "nombre": f"{palabra(rnd, 2).title()} {palabra(rnd, 3).title()}"
                      + ("é" if i % 17 == 0 else ""),
            "civ": i % n_civ,
            "matador": rnd.randrange(args.figuras),
            "causa": rnd.choice(["STRUCK", "OLD_AGE", "BLED", "DROWNED"]),
            "esfera": rnd.choice(["war", "death", "fortresses", "wealth", "nature"]),
            "objetivo": rnd.choice(["IMMORTALITY", "MASTER_A_SKILL", "RULE_THE_WORLD"]),
            "sitio": i % n_sitios,
            "enlace_hf": rnd.randrange(args.figuras) if rnd.random() < 0.3 else None,
            "tipo_enlace": rnd.choice(["spouse", "child", "parent", "friend", "deity"]),
            "habilidades": [(rnd.choice(HABILIDADES), rnd.randrange(100, 20000))
                            for _ in range(rnd.randint(1, 4))],
            "vinculo_sitio": rnd.choice(["seat of power", "home site building", "lair"]),
        })

    artefactos = []
    for a in range(args.artefactos):
        es_mio = a >= args.artefactos - 2
        artefactos.append({
            "id": a, "sitio": (n_sitios - 1) if es_mio else rnd.randrange(n_sitios - 1),
            "portador": rnd.randrange(args.figuras),
            "nombre": palabra(rnd, 3).title() + (SOL if a % 29 == 0 else ""),
            "material": rnd.choice(["steel", "bronze", "silver"]),
            "objeto": rnd.choice(["warhammer", "axe", "statue", "amulet", "book"]),
            "anyo": (anyo_final - 2) if es_mio else rnd.randrange(1, max(2, anyo_final - 45)),
        })

    # --- eventos, con identificador estable y anyo propio -------------------
    eventos = []

    def ev(anyo, tipo, campos):
        eventos.append({"id": len(eventos), "anyo": anyo, "tipo": tipo, "campos": campos})

    for sid, gob, civ in gobiernos:
        ev(sitios[sid]["fundado"], "created site",
           {"civ_id": civ, "site_civ_id": gob, "site_id": sid})
    for sid, gob, civ in gobiernos:
        if sid == n_sitios - 1:
            continue
        if rnd.random() < 0.18:
            ev(rnd.randrange(sitios[sid]["fundado"], anyo_final + 1), "site taken over",
               {"attacker_civ_id": rnd.randrange(n_civ), "defender_civ_id": civ,
                "site_civ_id": gob, "site_id": sid})
        if rnd.random() < 0.07:
            ev(rnd.randrange(sitios[sid]["fundado"], anyo_final + 1), "destroyed site",
               {"attacker_civ_id": rnd.randrange(n_civ), "defender_civ_id": civ, "site_id": sid})
    for f in figuras:
        if f["muerte"] != -1:
            ev(f["muerte"], "hf died",
               {"hfid": f["id"], "slayer_hfid": f["matador"], "cause": f["causa"],
                "site_id": f["sitio"]})
    for a in artefactos:
        ev(a["anyo"], "created artifact",
           {"artifact_id": a["id"], "hfid": a["portador"], "site_id": a["sitio"]})
    ev(anyo_final - 1, "attacked site",
       {"attacker_civ_id": 1 % n_civ, "defender_civ_id": 0, "site_id": n_sitios - 1})
    ev(anyo_final - 1, "artifact claim formed",
       {"artifact_id": artefactos[-1]["id"] if artefactos else 0,
        "entity_id": 1 % n_civ, "site_id": n_sitios - 1})
    tipos_relleno = ["merchant", "attacked site", "add hf entity link", "change hf state",
                     "hf simple battle event", "created structure", "item stolen",
                     "new site leader", "agreement made"]
    while len(eventos) < args.eventos:
        ev(rnd.randrange(1, anyo_final + 1), rnd.choice(tipos_relleno),
           {"site_id": rnd.randrange(n_sitios - 1), "hfid": rnd.randrange(args.figuras),
            "civ_id": rnd.randrange(n_civ), "attacker_civ_id": rnd.randrange(n_civ),
            "state": rnd.choice(["settled", "wandering", "visiting"])})
    eventos.sort(key=lambda e: (e["anyo"], e["id"]))

    guerras = []
    for c in range(args.guerras):
        atacante, defensor = rnd.sample(range(n_civ), 2)
        guerras.append({
            "id": c, "inicio": rnd.randrange(1, max(2, anyo_final)),
            "fin": -1 if c % 3 == 0 else rnd.randrange(1, anyo_final + 1),
            "nombre": f"the War of {palabra(rnd, 2).title()}",
            "atacante": atacante, "defensor": defensor,
        })

    # Las regiones salen de la geografia: cada mancha contigua de un bioma.
    regiones = geo["regiones"]

    # Calzadas, puentes y tuneles entre sitios cercanos, con recorrido en ele.
    construcciones = []
    for i in range(min(len(sitios) - 1, max(4, len(sitios) // 6))):
        a = sitios[i]
        b = min((s for s in sitios if s["id"] != a["id"]),
                key=lambda s: abs(s["x"] - a["x"]) + abs(s["y"] - a["y"]))
        camino = [(x, a["y"]) for x in range(min(a["x"], b["x"]), max(a["x"], b["x"]) + 1)]
        camino += [(b["x"], y) for y in range(min(a["y"], b["y"]), max(a["y"], b["y"]) + 1)]
        if len(camino) < 2:
            continue
        tipo = ["road", "bridge", "tunnel"][i % 3]
        construcciones.append({"id": len(construcciones), "tipo": tipo,
                               "nombre": f"the {tipo} of {palabra(rnd, 2)}",
                               "camino": camino})
    poblaciones = [(i, entidades[i]["raza"], rnd.randrange(200, 9000), i) for i in range(n_civ)]
    secretos = {f["id"] for f in figuras if f["id"] % 61 == 0}
    tramas = {f["id"]: rnd.choice(["corrupt", "sabotage", "infiltrate"])
              for f in figuras if f["id"] % 97 == 0}

    return {
        "entidades": entidades, "gobiernos": gobiernos, "sitios": sitios, "figuras": figuras,
        "artefactos": artefactos, "eventos": eventos, "guerras": guerras, "regiones": regiones,
        "poblaciones": poblaciones, "secretos": secretos, "tramas": tramas, "n_civ": n_civ,
        "geo": geo, "construcciones": construcciones,
    }


def recortar(mundo, args, anyo: int, con_fortaleza: bool):
    """Devuelve (principal, plus) con el estado del mundo en un anyo dado."""
    n_sitios = len(mundo["sitios"])
    ultima = n_sitios - 1
    sitios = [s for s in mundo["sitios"]
              if s["fundado"] <= anyo and (con_fortaleza or s["id"] != ultima)]
    visibles = {s["id"] for s in sitios}
    figuras = [f for f in mundo["figuras"] if f["nacimiento"] <= anyo]
    eventos = [e for e in mundo["eventos"]
               if e["anyo"] <= anyo and e["campos"].get("site_id", 0) in visibles]
    artefactos = [a for a in mundo["artefactos"] if a["anyo"] <= anyo and a["sitio"] in visibles]

    def campos(d):
        return "".join(f"<{k}>{v}</{k}>" for k, v in d.items())

    m = ['<?xml version="1.0" encoding=\'CP437\'?>', "<df_world>",
         f"<name>{args.mundo}</name>",
         f"<altname>The Universe of {args.mundo.title()}{SOL}</altname>", "<regions>"]
    for r in mundo["regiones"]:
        m.append(f"<region><id>{r['id']}</id><name>the region of {r['nombre']}</name>"
                 f"<type>{r['tipo']}</type></region>")
    m.append("</regions>")

    m.append("<sites>")
    for s in sitios:
        estructuras = "".join(
            f"<structure><local_id>{k}</local_id><type>{t}</type>"
            f"<name>the {t} of {s['nombre']}</name></structure>" for k, t in s["estructuras"])
        m.append(f"<site><id>{s['id']}</id><type>{s['tipo']}</type><n>{s['nombre']}</n>"
                 f"<coords>{s['x']},{s['y']}</coords>"
                 f"<rectangle>{s['x']},{s['y']}:{s['x']+1},{s['y']+1}</rectangle>"
                 f"<structures>{estructuras}</structures></site>")
    m.append("</sites>")

    m.append("<artifacts>")
    for a in artefactos:
        m.append(f"<artifact><id>{a['id']}</id><name>{a['nombre']}</name>"
                 f"<item><name_string>a {a['material']} {a['objeto']} named {a['nombre']}"
                 f"</name_string></item><site_id>{a['sitio']}</site_id>"
                 f"<holder_hfid>{a['portador']}</holder_hfid></artifact>")
    m.append("</artifacts>")

    m.append("<historical_figures>")
    for f in figuras:
        muerte = f["muerte"] if (f["muerte"] != -1 and f["muerte"] <= anyo) else -1
        enlaces = (f"<entity_link><entity_id>{f['civ']}</entity_id><link_type>member</link_type>"
                   f"<link_strength>60</link_strength></entity_link>")
        if f["enlace_hf"] is not None:
            enlaces += (f"<hf_link><hfid>{f['enlace_hf']}</hfid>"
                        f"<link_type>{f['tipo_enlace']}</link_type>"
                        f"<link_strength>50</link_strength></hf_link>")
        for hab, ip in f["habilidades"]:
            enlaces += f"<hf_skill><skill>{hab}</skill><total_ip>{ip}</total_ip></hf_skill>"
        m.append(
            f"<historical_figure><id>{f['id']}</id><name>{f['nombre']}</name>"
            f"<race>{f['raza']}</race><caste>{'FEMALE' if f['id'] % 2 else 'MALE'}</caste>"
            f"<appeared>{f['nacimiento']}</appeared>"
            f"<birth_year>{f['nacimiento']}</birth_year><birth_seconds>-1</birth_seconds>"
            f"<death_year>{muerte}</death_year><death_seconds>-1</death_seconds>"
            f"<associated_type>{f['tipo']}</associated_type>{enlaces}"
            f"<goal>{f['objetivo']}</goal></historical_figure>")
    m.append("</historical_figures>")

    m.append("<historical_events>")
    for e in eventos:
        m.append(f"<historical_event><id>{e['id']}</id><year>{e['anyo']}</year>"
                 f"<seconds72>{e['id'] % 1200}</seconds72><type>{e['tipo']}</type>"
                 f"{campos(e['campos'])}</historical_event>")
    m.append("</historical_events>")

    m.append("<historical_event_collections>")
    for g in mundo["guerras"]:
        if g["inicio"] > anyo:
            continue
        fin = g["fin"] if (g["fin"] != -1 and g["fin"] <= anyo) else -1
        m.append(f"<historical_event_collection><id>{g['id']}</id>"
                 f"<start_year>{g['inicio']}</start_year><end_year>{fin}</end_year>"
                 f"<type>war</type><name>{g['nombre']}</name>"
                 f"<attacking_enid>{g['atacante']}</attacking_enid>"
                 f"<defending_enid>{g['defensor']}</defending_enid>"
                 f"<event>0</event></historical_event_collection>")
    m.append("</historical_event_collections>")

    m.append("<entities>")
    for e in mundo["entidades"]:
        m.append(f"<entity><id>{e['id']}</id><name>{e['nombre']}</name></entity>")
    m.append("</entities>")
    m.append("</df_world>")

    # ------------------------------------------------------------------ plus
    p = ['<?xml version="1.0" encoding=\'CP437\'?>', "<df_world>",
         f"<name>{args.mundo}</name>", "<sites>"]
    for sid, gob, civ in mundo["gobiernos"]:
        if sid not in visibles:
            continue
        s = mundo["sitios"][sid]
        p.append(f"<site><id>{sid}</id><name>{s['nombre']}</name><type>{s['tipo']}</type>"
                 f"<coords>{s['x']},{s['y']}</coords><civ_id>{civ}</civ_id>"
                 f"<cur_owner_id>{gob}</cur_owner_id></site>")
    p.append("</sites>")
    p.append("<entities>")
    for e in mundo["entidades"]:
        hijos = "".join(f"<child>{c}</child>" for c in e["hijos"]
                        if c - mundo["n_civ"] in visibles)
        p.append(f"<entity><id>{e['id']}</id><n>{e['nombre']}</n><type>{e['tipo']}</type>"
                 f"<race>{e['raza']}</race>{hijos}"
                 f"<entity_position><id>0</id><name>lider</name></entity_position>"
                 f"<entity_position_assignment><id>0</id><position_id>0</position_id>"
                 f"<histfig>{e['id'] % max(1, len(mundo['figuras']))}</histfig>"
                 f"</entity_position_assignment></entity>")
    p.append("</entities>")
    p.append("<historical_figures>")
    for f in figuras:
        extras = ""
        if f["id"] in mundo["secretos"]:
            extras += "<interaction_knowledge>SECRET_OF_LIFE_AND_DEATH</interaction_knowledge>"
        if f["id"] in mundo["tramas"]:
            extras += (f"<intrigue_plot><type>{mundo['tramas'][f['id']]}</type>"
                       f"<agreement_id>{f['id']}</agreement_id>"
                       f"<parent_plot_hfid>{max(0, f['id'] - 1)}</parent_plot_hfid></intrigue_plot>")
        sitio = f["sitio"] if f["sitio"] in visibles else next(iter(visibles))
        p.append(f"<historical_figure><id>{f['id']}</id><sphere>{f['esfera']}</sphere>{extras}"
                 f"<site_link><link_type>{f['vinculo_sitio']}</link_type>"
                 f"<site_id>{sitio}</site_id></site_link></historical_figure>")
    p.append("</historical_figures>")
    # La geometria del mundo va en el _plus, igual que en los exports reales:
    # el principal dice como se llama cada region y este dice donde esta.
    p.append("<regions>")
    for r in mundo["regiones"]:
        coords = "|".join(f"{x},{y}" for x, y in r["casillas"])
        p.append(f"<region><id>{r['id']}</id><coords>{coords}</coords>"
                 f"<evilness>{['neutral', 'good', 'evil'][r['id'] % 3]}"f"</evilness></region>")
    p.append("</regions>")

    p.append("<rivers>")
    for i, rio in enumerate(mundo["geo"]["rios"]):
        # Formato real: cada punto es x,y,caudal,salida,altura, y NO solo x,y.
        # Es la trampa que llenaba el mapa de rayas al leer pares sueltos a lo
        # largo de todo el texto. El caudal sube rio abajo y la altura baja.
        tramos = []
        for k, (x, y) in enumerate(rio["camino"]):
            caudal = 0 if k < 2 else int((k - 1) * 60 * (1 + i % 3))
            altura = 140 - k * 3
            tramos.append(f"{x},{y},{caudal},{k % 9},{altura}")
        camino = "|".join(tramos) + "|"
        fin = rio["camino"][-1]
        p.append(f"<river><name>the river of {rio['nombre']}</name>"
                 f"<path>{camino}</path>"
                 f"<end_pos>{fin[0]},{fin[1]}</end_pos></river>")
    p.append("</rivers>")

    p.append("<world_constructions>")
    for c in mundo["construcciones"]:
        coords = "|".join(f"{x},{y}" for x, y in c["camino"]) + "|"
        p.append(f"<world_construction><id>{c['id']}</id><name>{c['nombre']}</name>"
                 f"<type>{c['tipo']}</type><coords>{coords}</coords></world_construction>")
    p.append("</world_constructions>")

    p.append("<mountain_peaks>")
    for pico in mundo["geo"]["picos"]:
        p.append(f"<mountain_peak><id>{pico['id']}</id>"
                 f"<name>the peak of {pico['nombre']}</name>"
                 f"<coords>{pico['x']},{pico['y']}</coords>"
                 f"<height>{pico['altura']}</height>"
                 + ("<is_volcano />" if pico["volcan"] else "")
                 + "</mountain_peak>")
    p.append("</mountain_peaks>")

    p.append("<entity_populations>")
    for i, raza, cuenta, civ in mundo["poblaciones"]:
        p.append(f"<entity_population><id>{i}</id><race>{raza}</race>"
                 f"<count>{cuenta}</count><civ_id>{civ}</civ_id></entity_population>")
    p.append("</entity_populations>")
    p.append("</df_world>")

    return "\n".join(m), "\n".join(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("destino", nargs="?", default="data/imports")
    ap.add_argument("--mundo", default="ozorothsanreg", help="nombre interno del mundo")
    ap.add_argument("--token", default="sample1", help="prefijo del nombre de fichero")
    ap.add_argument("--tam", type=int, default=40, help="lado del mapa en casillas")
    ap.add_argument("--sitios", type=int, default=24)
    ap.add_argument("--figuras", type=int, default=180)
    ap.add_argument("--eventos", type=int, default=900)
    ap.add_argument("--artefactos", type=int, default=30)
    ap.add_argument("--guerras", type=int, default=6)
    ap.add_argument("--civilizaciones", type=int, default=5)
    ap.add_argument("--solo-uno", action="store_true",
                    help="genera un único export en lugar de dos fechas")
    ap.add_argument("--anyo-final", type=int, default=160, dest="anyo_final")
    args = ap.parse_args()

    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)

    anyo_previo = max(1, args.anyo_final - 40)
    fechas = [(f"{anyo_previo:05d}-01-01", anyo_previo, False),
              (f"{args.anyo_final:05d}-07-24", args.anyo_final, True)]
    if args.solo_uno:
        fechas = fechas[-1:]

    mundo = construir_mundo(args)
    for fecha, anyo, fort in fechas:
        prefijo = f"{args.token}-{fecha}"
        principal, plus = recortar(mundo, args, anyo, fort)
        rp = destino / f"{prefijo}-legends.xml"
        rs = destino / f"{prefijo}-legends_plus.xml"
        rp.write_bytes(principal.encode("cp437", errors="replace"))
        rs.write_bytes(plus.encode("cp437", errors="replace"))
        print(f"generado {prefijo}: {rp.stat().st_size/1048576:.1f} MB + "
              f"{rs.stat().st_size/1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
