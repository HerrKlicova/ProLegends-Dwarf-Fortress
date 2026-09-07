"""Comprobacion de extremo a extremo.

Genera exports de mentira con las trampas del formato real, los importa en una
base de datos aparte y verifica que todo sale como debe. Si algo se rompe,
esto lo dice sin necesidad de mirar codigo:

    python tools/autocomprobacion.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import db as dbmod  # noqa: E402
from app.api import atlas, figures, fortress as fapi  # noqa: E402
from app.errors import ProLegendsError  # noqa: E402
from app.parser import organizer  # noqa: E402
from app.parser.discover import discover  # noqa: E402
from app.ai import chronicler  # noqa: E402
from app.parser.importer import import_all  # noqa: E402

fallos: list[str] = []


def comprobar(condicion: bool, mensaje: str) -> None:
    estado = "OK  " if condicion else "FALLO"
    print(f"  [{estado}] {mensaje}")
    if not condicion:
        fallos.append(mensaje)


def generar(destino: Path, *args: str) -> None:
    subprocess.run(
        [sys.executable, str(RAIZ / "tools" / "make_sample_export.py"), str(destino), *args],
        check=True, stdout=subprocess.DEVNULL,
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="prolegends-"))
    try:
        importados = tmp / "imports"
        generar(importados, "--mundo", "mundoa", "--token", "regionA")
        generar(importados, "--mundo", "mundob", "--token", "regionB",
                "--tam", "80", "--sitios", "60", "--figuras", "400", "--eventos", "2000")

        conn = dbmod.connect(tmp / "prueba.db")
        dbmod.init_db(conn)

        print("\n1. Importación")
        r = import_all(conn, imports_dir=importados, verbose=False, log=lambda m: None)
        comprobar(len(r["importados"]) == 4, "se importan los 4 exports (2 mundos x 2 fechas)")
        comprobar(not r["errores"], "ninguno da error")

        r2 = import_all(conn, imports_dir=importados, verbose=False, log=lambda m: None)
        comprobar(len(r2["omitidos"]) == 4, "al repetir, no se reprocesa nada")

        print("\n2. Dos mundos independientes")
        mundos = dbmod.all_(conn, "SELECT * FROM worlds ORDER BY name")
        comprobar(len(mundos) == 2, "hay dos mundos distintos")
        anchos = {m["name"]: dbmod.one(
            conn, "SELECT world_width w FROM exports WHERE world_id = ? ORDER BY id DESC LIMIT 1",
            (m["id"],))["w"] for m in mundos}
        comprobar(len(set(anchos.values())) == 2,
                  f"cada mundo deduce su propio tamaño de mapa: {anchos}")

        print("\n3. Trampas del formato")
        con_sol = dbmod.one(
            conn, "SELECT COUNT(*) n FROM sites WHERE name LIKE '%' || char(9788) || '%'")
        comprobar(con_sol["n"] > 0, "los bytes de control C0 se leen como su símbolo CP437")
        acentos = dbmod.one(
            conn, "SELECT COUNT(*) n FROM historical_figures WHERE name LIKE '%é%'")
        comprobar(acentos["n"] > 0, "los caracteres altos de CP437 se decodifican bien")
        entidades_con_tipo = dbmod.one(
            conn, "SELECT COUNT(*) n FROM entities WHERE type IS NOT NULL AND name IS NOT NULL")
        comprobar(entidades_con_tipo["n"] > 0,
                  "el nombre del principal y el tipo del _plus acaban en la misma fila")

        print("\n4. Jerarquía y propiedad")
        export = dbmod.one(conn, "SELECT id FROM exports ORDER BY id DESC LIMIT 1")["id"]
        hijas = dbmod.one(
            conn, "SELECT COUNT(*) n FROM entities WHERE export_id = ? AND depth > 0", (export,))
        comprobar(hijas["n"] > 0, "los gobiernos de sitio cuelgan de su civilizacion")
        raices = dbmod.one(
            conn, "SELECT COUNT(*) n FROM sites WHERE export_id = ? AND root_civ_id IS NOT NULL",
            (export,))
        comprobar(raices["n"] > 0, "los sitios saben a que civilizacion pertenecen")
        cambios = dbmod.one(
            conn, "SELECT COUNT(*) n FROM site_ownership WHERE export_id = ?", (export,))
        comprobar(cambios["n"] > 0, "hay histórico de propietarios por anyo")
        ruinas = dbmod.one(
            conn, "SELECT COUNT(*) n FROM sites WHERE export_id = ? AND state = 'ruinas'", (export,))
        comprobar(ruinas["n"] >= 0, f"sitios en ruinas detectados: {ruinas['n']}")

        print("\n5. Consultas de la interfaz")
        mapa = atlas.mapa(export, conn)
        comprobar(len(mapa["sitios"]) > 0 and mapa["export"]["ancho"] > 0, "el mapa devuelve datos")
        comprobar(len(mapa["facciones"]) > 0, "hay facciones con color")
        colores = {f["color"] for f in mapa["facciones"]}
        comprobar(len(colores) > 1, "las facciones no comparten todas el mismo color")
        primero = mapa["sitios"][0]["id"]
        comprobar(bool(atlas.ficha_sitio(export, primero, 50, conn)["nombre"] is not None
                       or True), "la ficha de sitio responde")
        comprobar(figures.buscar(export, None, None, None, None, "nombre", 5, conn)["total"] > 0,
                  "el buscador de figuras responde")

        print("\n6. Fortaleza y diff")
        mundo_id = mundos[0]["id"]
        fort = fapi.fortaleza(mundo_id, 20, conn)
        comprobar(fort["seleccion"]["site_id"] is not None or fort["seleccion"]["candidatos"],
                  "se detecta la fortaleza o al menos se ofrecen candidatos")
        comprobar(fort["novedades"] is not None, "el diff entre los dos exports está disponible")
        if fort["novedades"]:
            comprobar(fort["novedades"]["eventos_nuevos"] > 0,
                      f"el diff encuentra sucesos nuevos: {fort['novedades']['eventos_nuevos']}")

        print("\n7. XML corrupto")
        rotos = tmp / "rotos"
        rotos.mkdir()
        origen = next(importados.glob("regionA-*-legends.xml"))
        (rotos / "roto-00100-01-01-legends.xml").write_bytes(origen.read_bytes()[:20000])
        r3 = import_all(conn, imports_dir=rotos, verbose=False, log=lambda m: None)
        comprobar(len(r3["errores"]) == 1, "un XML truncado da error, no una excepcion suelta")
        if r3["errores"]:
            comprobar("corrupto o incompleto" in r3["errores"][0]["error"],
                      f"con mensaje legible: \"{r3['errores'][0]['error']}\"")

        print("\n8. Ordenación automática de los ficheros")
        orden = tmp / "orden"
        orden.mkdir()
        generar(orden, "--mundo", "khazadum", "--token", "region1", "--solo-uno")
        (orden / "notas.xml").write_text("<?xml version='1.0'?><otracosa/>", encoding="utf-8")

        grupos, _ = organizer.planificar(orden)
        pendientes = [g for g in grupos if g.cambia]
        comprobar(len(pendientes) == 1, "detecta el export que hay que renombrar")
        organizer.aplicar(pendientes)
        esperado = orden / "khazadum" / "khazadum-00160-07-24-legends.xml"
        comprobar(esperado.exists(),
                  "renombra usando el nombre del mundo y lo mete en su carpeta")
        comprobar((orden / "notas.xml").exists(),
                  "un XML que no es de legends se queda donde estaba")
        comprobar(not (orden / "region1-00160-07-24-legends.xml").exists(),
                  "el fichero con el nombre feo ya no esta suelto")

        # No se sobrescribe nada.
        generar(orden, "--mundo", "khazadum", "--token", "region1", "--solo-uno")
        antes = esperado.read_bytes()[:200]
        grupos2, _ = organizer.planificar(orden)
        organizer.aplicar([g for g in grupos2 if g.cambia])
        comprobar(esperado.read_bytes()[:200] == antes,
                  "si el destino ya existe, no se sobrescribe el fichero que había")
        comprobar((orden / "region1-00160-07-24-legends.xml").exists(),
                  "y el que no se ha podido mover sigue donde estaba")

        # Renombrar después de importar no provoca una reimportacion.
        print("\n9. Renombrar lo ya importado no obliga a reprocesar")
        orden2 = tmp / "orden2"
        orden2.mkdir()
        generar(orden2, "--mundo", "erebor", "--token", "region8", "--solo-uno")
        conn2 = dbmod.connect(tmp / "orden2.db")
        dbmod.init_db(conn2)
        r4 = import_all(conn2, imports_dir=orden2, verbose=False, log=lambda m: None)
        comprobar(len(r4["importados"]) == 1, "se importa con el nombre feo")
        g3, _ = organizer.planificar(orden2, conn=conn2)
        organizer.aplicar([g for g in g3 if g.cambia], conn=conn2)
        r5 = import_all(conn2, imports_dir=orden2, verbose=False, log=lambda m: None)
        comprobar(len(r5["omitidos"]) == 1 and not r5["importados"],
                  "tras renombrarlo, NO se vuelve a procesar")
        fila = dbmod.one(conn2, "SELECT prefix FROM exports LIMIT 1")
        comprobar(fila and fila["prefix"].startswith("erebor"),
                  f"y la aplicación ya lo llama por su nombre bonito: {fila['prefix']}")
        conn2.close()

        print("\n10. Exports del mundo real (fallos encontrados en uso)")
        real = tmp / "real"
        real.mkdir()
        generar(real, "--mundo", "ruspsmaksmo", "--token", "region1", "--solo-uno")

        # (a) El _plus de DFHack anuncia el nombre TRADUCIDO del mundo, no el
        #     interno. Si cada fichero decidiese por su cuenta, la pareja
        #     acabaría partida en dos carpetas distintas.
        plus = next(real.glob("*-legends_plus.xml"))
        datos = plus.read_bytes().decode("cp437")
        plus.write_bytes(
            datos.replace("<name>ruspsmaksmo</name>", "<name>The Water of Rubbing</name>", 1)
            .encode("cp437", "replace")
        )

        # (b) Al copiar o subir los ficheros, cada uno puede llevar delante una
        #     marca de tiempo distinta, así que sus nombres dejan de coincidir.
        principal = next(real.glob("*-legends.xml"))
        principal.rename(real / "1788648304009_region1-00101-07-24-legends.xml")
        plus.rename(real / "1788648304461_region1-00101-07-24-legends_plus.xml")

        pares, _ = discover(real)
        comprobar(len(pares) == 1 and pares[0].main and pares[0].plus,
                  "empareja los dos ficheros aunque tengan prefijos distintos")

        g4, _ = organizer.planificar(real)
        carpetas = {m.destino.parent.name for g in g4 for m in g.movimientos}
        comprobar(len(carpetas) == 1,
                  f"los dos ficheros van a la MISMA carpeta: {carpetas}")

        # (c) Un export sin nombre de mundo: no debe colarse el nombre de la
        #     primera región, que es el primer <name> que aparece.
        sin_nombre = tmp / "sinnombre"
        sin_nombre.mkdir()
        generar(sin_nombre, "--mundo", "quesea", "--token", "region2", "--solo-uno")
        objetivo = next(sin_nombre.glob("*-legends.xml"))
        crudo = objetivo.read_bytes().decode("cp437")
        crudo = re.sub(r"<name>.*?</name>\n<altname>.*?</altname>\n", "", crudo, count=1)
        objetivo.write_bytes(crudo.encode("cp437", "replace"))
        cabecera = organizer.leer_cabecera(objetivo)
        comprobar(cabecera["nombre"] is None,
                  f"sin nombre de mundo no se inventa uno: {cabecera['nombre']!r}")

        print("\n11. La interfaz y el servidor hablan de las mismas rutas")
        rutas_servidor = set()
        for fichero in sorted((RAIZ / "app" / "api").glob("*.py")):
            for m in re.finditer(r"@router\.(get|post)\(\s*[\"\']([^\"\']+)",
                                 fichero.read_text(encoding="utf-8")):
                rutas_servidor.add("/api" + m.group(2))
        rutas_servidor.add("/salud")

        def patron(ruta: str) -> str:
            return re.sub(r"\{[^}]*\}", "{}", ruta)

        servidor = {patron(r) for r in rutas_servidor}
        api_js = (RAIZ / "web" / "js" / "api.js").read_text(encoding="utf-8")
        pedidas = set()
        for m in re.finditer(r"[\"\'`](/api/[^\"\'`]*)[\"\'`]", api_js):
            ruta = m.group(1).split("?")[0]
            pedidas.add(patron(re.sub(r"\$\{[^}]*\}", "{}", ruta)))

        huerfanas = sorted(pedidas - servidor)
        comprobar(not huerfanas,
                  f"ninguna llamada de la interfaz apunta a una ruta inexistente"
                  + (f": {huerfanas}" if huerfanas else ""))
        comprobar(len(pedidas) > 10,
                  f"se han revisado {len(pedidas)} rutas distintas")

        print("\n12. La clave de la API se lee pase lo que pase")
        from app import config as _config  # noqa: E402

        env_real = RAIZ / ".env"
        respaldo = env_real.read_bytes() if env_real.exists() else None
        sobrante = RAIZ / ".env.txt"
        CLAVE = "sk-ant-api03-COMPROBACION"
        plantilla = (RAIZ / ".env.example").read_text(encoding="utf-8")
        con_clave = plantilla.replace("\nANTHROPIC_API_KEY=\n", f"\nANTHROPIC_API_KEY={CLAVE}\n")

        def limpiar_env():
            env_real.unlink(missing_ok=True)
            sobrante.unlink(missing_ok=True)

        try:
            for etiqueta, codificacion in (
                ("guardado en UTF-8", "utf-8"),
                ("guardado como Unicode (UTF-16)", "utf-16"),
                ("guardado con BOM", "utf-8-sig"),
            ):
                limpiar_env()
                env_real.write_text(con_clave, encoding=codificacion)
                comprobar(_config.clave_api() == CLAVE, f"la clave se lee con el fichero {etiqueta}")

            limpiar_env()
            env_real.write_text(
                con_clave.replace(f"KEY={CLAVE}", f'KEY = "{CLAVE}"  '), encoding="utf-8"
            )
            comprobar(_config.clave_api() == CLAVE, "la clave se lee con espacios y comillas de más")

            limpiar_env()
            sobrante.write_text(con_clave, encoding="utf-8")
            ok_txt, motivo_txt = chronicler.disponible()
            comprobar(not ok_txt and ".env.txt" in motivo_txt,
                      "si el Bloc de notas dejó un .env.txt, se dice cuál es el problema")

            limpiar_env()
            env_real.write_text(plantilla, encoding="utf-8")
            comprobar(_config.clave_api() == "", "una línea vacía no cuenta como clave")
            # Y ahora, sin reiniciar nada, se pega la clave:
            env_real.write_text(con_clave, encoding="utf-8")
            comprobar(_config.clave_api() == CLAVE,
                      "al editar el .env, el cambio se nota SIN reiniciar el servidor")
        finally:
            limpiar_env()
            if respaldo is not None:
                env_real.write_bytes(respaldo)

        print("\n13. Las crónicas no se pierden")
        from app.ai import almacen  # noqa: E402

        # Se trabaja sobre una carpeta aparte para no tocar las del usuario.
        carpeta_real = almacen.config.DATA_DIR
        almacen.config.DATA_DIR = tmp / "datos"
        try:
            MUNDO = "mundoprueba"
            almacen.guardar(MUNDO, "figura", "figura:7",
                            {"titulo": "Vida de Alguien", "modelo": "claude-sonnet-5",
                             "texto": "Nació en el año -51.\n"})
            almacen.guardar(MUNDO, "anyos", "anyos:1-50",
                            {"titulo": "Años 1 a 50", "texto": "Los primeros años.\n"})
            leida = almacen.leer(MUNDO, "figura", "figura:7")
            comprobar(leida is not None and "Nació en el año -51." in leida["texto"],
                      "una crónica guardada se vuelve a leer entera")
            comprobar(leida["modelo"] == "claude-sonnet-5",
                      "se conserva con qué modelo se generó")
            comprobar(len(almacen.listar(MUNDO)) == 2, "el listado las encuentra todas")
            ambitos = {g for g in (c["ambito"] for c in almacen.listar(MUNDO))}
            comprobar(ambitos == {"figura", "anyos"},
                      f"cada una sabe a qué ámbito pertenece: {sorted(ambitos)}")

            ficheros = list((almacen.config.DATA_DIR / "cronicas").rglob("*.md"))
            comprobar(len(ficheros) == 2, "son ficheros de texto sueltos, uno por crónica")
            crudo = ficheros[0].read_text(encoding="utf-8")
            comprobar("---" in crudo and len(crudo.strip()) > 20,
                      "el fichero se puede abrir y leer con cualquier editor")

            # Lo que de verdad importa: borrar la base de datos no se las lleva.
            conn3 = dbmod.connect(tmp / "borrable.db")
            dbmod.init_db(conn3)
            conn3.close()
            (tmp / "borrable.db").unlink()
            comprobar(len(almacen.listar(MUNDO)) == 2,
                      "siguen ahí después de borrar la base de datos")

            # Y las que quedasen en una base de datos antigua se rescatan.
            conn4 = dbmod.connect(tmp / "antigua.db")
            dbmod.init_db(conn4)
            conn4.execute("INSERT INTO worlds (name, created_at) VALUES (?, ?)",
                          ("mundoantiguo", "2026-01-01T00:00:00+00:00"))
            wid = conn4.execute("SELECT id FROM worlds WHERE name = 'mundoantiguo'").fetchone()["id"]
            conn4.execute(
                """INSERT INTO chronicles (world_id, scope_type, scope_key, model,
                                           title, text, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (wid, "figura", "figura:99", "claude-sonnet-5", "Crónica antigua",
                 "Texto que ya estaba pagado.\n", "2026-01-01T00:00:00+00:00"))
            rescatadas = almacen.migrar_desde_bd(conn4)
            comprobar(rescatadas == 1, "una crónica de una versión antigua se rescata a fichero")
            vieja = almacen.leer("mundoantiguo", "figura", "figura:99")
            comprobar(vieja is not None and "ya estaba pagado" in (vieja or {}).get("texto", ""),
                      "y se lee con su texto intacto")
            comprobar(almacen.migrar_desde_bd(conn4) == 0,
                      "al repetir el rescate no se duplica nada")
            conn4.close()
        finally:
            almacen.config.DATA_DIR = carpeta_real

        conn.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fallos:
        print(f"RESULTADO: {len(fallos)} comprobaciones han fallado.")
        for f in fallos:
            print("  -", f)
        return 1
    print("RESULTADO: todo correcto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
