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
import time
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

        # La interfaz lleva escrita su propia version para poder avisar cuando
        # el navegador sirve de su cache una version anterior. Si ese numero se
        # queda atras, el aviso saltaria siempre y dejaria de significar nada.
        import app as paquete  # noqa: E402

        en_js = re.search(r"VERSION_INTERFAZ\s*=\s*['\"]([\d.]+)", api_js + (
            RAIZ / "web" / "js" / "app.js").read_text(encoding="utf-8"))
        en_main = re.search(r'version="([\d.]+)"',
                            (RAIZ / "app" / "main.py").read_text(encoding="utf-8"))
        comprobar(en_js is not None and en_main is not None
                  and en_js.group(1) == paquete.__version__ == en_main.group(1),
                  f"la version coincide en los tres sitios: paquete {paquete.__version__}, "
                  f"servidor {en_main and en_main.group(1)}, interfaz {en_js and en_js.group(1)}")

        # Y el servidor tiene que pedirle al navegador que no se quede con la
        # interfaz vieja. Sin esto, actualizar ProLegends parecia no hacer nada.
        import socket  # noqa: E402
        import urllib.request  # noqa: E402

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            puerto = s.getsockname()[1]
        servidor = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--port", str(puerto), "--log-level", "critical"],
            cwd=str(RAIZ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            cabeceras = {}
            for _ in range(60):
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{puerto}/js/app.js", timeout=2
                    ) as r:
                        cabeceras = {k.lower(): v for k, v in r.headers.items()}
                    break
                except OSError:
                    time.sleep(0.4)
            comprobar("no-cache" in cabeceras.get("cache-control", ""),
                      f"la interfaz se sirve sin caché: {cabeceras.get('cache-control')!r}")
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)

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

        print("\n14. Se lee bien tanto UTF-8 como CP437")
        from app.parser.xmlstream import SanitizedXMLStream, detectar_codificacion  # noqa: E402

        # DFHack escribe los exports actuales en UTF-8; los antiguos, en CP437.
        # Hay que acertar con los dos, y sin fiarse solo de lo que declaren.
        NOMBRE = "Joñu Olngö Ngôrdax"
        cuerpo = (
            '<df_world>\n<name>mundoacentos</name>\n<altname>Tierra de Ñ</altname>\n'
            f'<historical_figures><historical_figure><id>0</id><name>{NOMBRE}</name>'
            '<race>DWARF</race></historical_figure></historical_figures>\n</df_world>\n'
        )
        acentos = tmp / "acentos"
        acentos.mkdir()

        en_utf8 = acentos / "utf8-00001-01-01-legends.xml"
        en_utf8.write_bytes(
            ('<?xml version="1.0" encoding=\'UTF-8\'?>\n' + cuerpo).encode("utf-8")
        )
        comprobar(detectar_codificacion(en_utf8) == "utf-8", "un export en UTF-8 se detecta como UTF-8")
        flujo = SanitizedXMLStream(en_utf8)
        leido = flujo.read().decode("utf-8"); flujo.close()
        comprobar(NOMBRE in leido, f"y sus nombres se leen intactos: {NOMBRE}")

        en_cp437 = acentos / "cp437-00001-01-01-legends.xml"
        en_cp437.write_bytes(
            ('<?xml version="1.0" encoding=\'CP437\'?>\n'
             + cuerpo.replace(NOMBRE, "René \x0fMartillo\x0f")).encode("cp437", "replace")
        )
        comprobar(detectar_codificacion(en_cp437) == "cp437", "un export en CP437 se detecta como CP437")
        flujo = SanitizedXMLStream(en_cp437)
        leido = flujo.read().decode("utf-8"); flujo.close()
        comprobar("René" in leido and "☼Martillo☼" in leido,
                  "y conserva sus acentos y sus símbolos del sol")

        # El caso peligroso: que el fichero mienta sobre su codificación.
        mentiroso = acentos / "mentira-00001-01-01-legends.xml"
        mentiroso.write_bytes(
            ('<?xml version="1.0" encoding=\'CP437\'?>\n' + cuerpo).encode("utf-8")
        )
        comprobar(detectar_codificacion(mentiroso) == "utf-8",
                  "si declara CP437 pero es UTF-8, se hace caso al contenido, no a la declaración")

        print("\n15. La carpeta de Dwarf Fortress")
        from app import ajustes as ajustesmod, config as cfg, juego as juegomod  # noqa: E402

        # Se imita la carpeta real del juego: el ejecutable y los XML sueltos
        # al lado, que es donde DF los deja al exportar.
        carpeta_df = tmp / "Dwarf Fortress"
        carpeta_df.mkdir()
        (carpeta_df / juegomod.EJECUTABLE).write_bytes(b"MZ falso")
        (carpeta_df / "world_map.bmp").write_bytes(b"BM falso")
        generar(carpeta_df, "--mundo", "Ruspsmaksmo", "--token", "region1",
                "--solo-uno", "--anyo-final", "103")

        comprobar(juegomod.es_carpeta_df(carpeta_df),
                  "se reconoce la carpeta del juego por su ejecutable")
        cualquiera = tmp / "cualquiera"
        cualquiera.mkdir()
        (cualquiera / "notas.txt").write_text("nada que ver", encoding="utf-8")
        comprobar(not juegomod.es_carpeta_df(cualquiera),
                  "una carpeta cualquiera no se confunde con la del juego")
        # A propósito se acepta también una carpeta sin ejecutable pero con
        # exports dentro: hay quien se los guarda aparte o no usa Steam.
        comprobar(juegomod.es_carpeta_df(tmp / "acentos"),
                  "y se acepta una carpeta que solo tenga exports de leyendas")

        destino_falso = tmp / "imports-juego"
        destino_falso.mkdir()
        datos_reales, imports_reales = cfg.DATA_DIR, cfg.IMPORTS_DIR
        cfg.DATA_DIR, cfg.IMPORTS_DIR = tmp, destino_falso
        try:
            hallados = juegomod.exports_en(carpeta_df)
            comprobar(len(hallados) == 1 and hallados[0]["completo"],
                      "encuentra el export completo (principal + _plus) en la carpeta del juego")
            comprobar(hallados[0]["mundo"] == "Ruspsmaksmo",
                      f"y le saca el nombre del mundo: {hallados[0]['mundo']!r}")
            comprobar((hallados[0]["anyo"], hallados[0]["mes"], hallados[0]["dia"]) == (103, 7, 24),
                      "y la fecha de la partida")
            comprobar(not hallados[0]["ya_en_imports"],
                      "y sabe que todavía no está en data/imports")
            comprobar(juegomod.mapas_en(carpeta_df) == ["world_map.bmp"],
                      "localiza también las imágenes de mapa que deje el juego")

            resultado = juegomod.traer(carpeta_df, [hallados[0]["prefijo"]], log=lambda m: None)
            comprobar(resultado["traidos"] == [hallados[0]["prefijo"]] and not resultado["fallos"],
                      "trae el export a data/imports sin errores")
            comprobar(len(list(destino_falso.glob("*.xml"))) == 2,
                      "llegan los dos ficheros, no solo uno")
            comprobar(len(list(carpeta_df.glob("*.xml"))) == 2,
                      "y los originales siguen en la carpeta del juego (se copia, no se mueve)")
            comprobar(juegomod.exports_en(carpeta_df)[0]["ya_en_imports"],
                      "a la segunda ya sabe que ese export lo tienes")

            pares_traidos, _ = discover(destino_falso)
            comprobar(len(pares_traidos) == 1 and pares_traidos[0].complete,
                      "y lo traído es un par válido, listo para importar")

            juegomod.recordar(carpeta_df)
            comprobar(juegomod.carpeta_recordada() == carpeta_df,
                      "la carpeta se recuerda entre arranques")
            comprobar(ajustesmod.ruta().exists() and "carpeta_df" in ajustesmod.leer(),
                      "guardada en data/ajustes.json, fuera de la base de datos")
            juegomod.olvidar()
            comprobar(juegomod.carpeta_recordada() is None, "y se puede olvidar")
        finally:
            cfg.DATA_DIR, cfg.IMPORTS_DIR = datos_reales, imports_reales

        print("\n16. Tus cosas sobreviven a bajarse una versión nueva")
        import os  # noqa: E402

        from app import config as cfg2, mudanza  # noqa: E402

        vieja = tmp / "ProLegends-version-anterior"
        personal = tmp / "MisDocumentos" / "ProLegends"
        (vieja / "data" / "cronicas" / "Ruspsmaksmo").mkdir(parents=True)
        (vieja / "data" / "cronicas" / "Ruspsmaksmo" / "anyos-1-50.md").write_text(
            "---\nmundo: Ruspsmaksmo\n---\nEn el año 1 nació Olngö.\n", encoding="utf-8")
        (vieja / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-api03-DEPRUEBA\n", encoding="utf-8")
        (vieja / "data" / "ajustes.json").write_text('{"carpeta_df": "D:/Steam"}', encoding="utf-8")
        (vieja / "data" / "imports").mkdir(parents=True)
        generar(vieja / "data" / "imports", "--mundo", "Ruspsmaksmo", "--token", "region1",
                "--solo-uno", "--anyo-final", "103")
        (vieja / "data" / "db").mkdir(parents=True)
        conn5 = dbmod.connect(vieja / "data" / "db" / "prolegends.db")
        dbmod.init_db(conn5)
        conn5.execute("INSERT INTO worlds(name, altname, created_at) "
                      "VALUES ('Ruspsmaksmo', 'The Universe', '2026-01-01')")
        conn5.close()

        guardado = (cfg2.BASE_DIR, cfg2.DATA_DIR_ANTIGUA, cfg2.DATA_DIR,
                    cfg2.IMPORTS_DIR, cfg2.DB_DIR, cfg2.DB_PATH,
                    os.environ.get("PROLEGENDS_HOME"))
        cfg2.BASE_DIR = vieja
        cfg2.DATA_DIR_ANTIGUA = vieja / "data"
        cfg2.DATA_DIR = personal
        cfg2.IMPORTS_DIR = personal / "imports"
        cfg2.DB_DIR = personal / "db"
        cfg2.DB_PATH = personal / "db" / "prolegends.db"
        os.environ["PROLEGENDS_HOME"] = str(personal)
        try:
            mudanza.migrar(log=lambda m: None)

            cronica = personal / "cronicas" / "Ruspsmaksmo" / "anyos-1-50.md"
            comprobar(cronica.exists() and "Olngö" in cronica.read_text(encoding="utf-8"),
                      "las crónicas llegan a la carpeta personal, con sus acentos")
            comprobar((vieja / "data" / "cronicas" / "Ruspsmaksmo" / "anyos-1-50.md").exists(),
                      "y las originales se quedan de respaldo: no se borra nada")
            comprobar("DEPRUEBA" in (personal / ".env").read_text(encoding="utf-8"),
                      "la clave de la API viaja sola")
            comprobar((personal / "ajustes.json").exists(), "los ajustes viajan")
            conn6 = dbmod.connect(personal / "db" / "prolegends.db")
            traido = conn6.execute("SELECT name FROM worlds").fetchone()
            conn6.close()
            comprobar(traido is not None and traido[0] == "Ruspsmaksmo",
                      "la base de datos viaja entera: no hay que reimportar 45 MB")
            movidos = sorted((personal / "imports").rglob("*.xml"))
            comprobar(len(movidos) == 2, f"los exports se mueven ({len(movidos)} ficheros)")
            comprobar(not list((vieja / "data" / "imports").rglob("*.xml")),
                      "y no se quedan ocupando sitio por duplicado")
            comprobar(mudanza.migrar(log=lambda m: None) == [],
                      "a la segunda vez ya no hay nada que mover")
            comprobar(cfg2.ruta_env() == vieja / ".env",
                      "el .env de la carpeta del programa sigue mandando mientras tenga clave")
            (vieja / ".env").write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")
            comprobar(cfg2.clave_api().endswith("DEPRUEBA"),
                      "y si ese se queda vacío, se usa el de la carpeta personal")

            # El caso de verdad: no se actualiza encima, se descomprime la
            # version nueva en otra carpeta. Las cronicas de la anterior estan
            # entonces en un sitio del que la nueva no sabe nada.
            descargas = tmp / "Descargas"
            anterior = descargas / "ProLegends-Dwarf-Fortress-1.3.1"
            recien = descargas / "ProLegends-Dwarf-Fortress-1.3.2"
            (anterior / "app").mkdir(parents=True)
            (anterior / "data" / "cronicas" / "Momuzosith").mkdir(parents=True)
            (anterior / "data" / "cronicas" / "Momuzosith" / "figura-7.md").write_text(
                "---\nmundo: Momuzosith\n---\nLa gesta de Ngôrdax.\n", encoding="utf-8")
            (anterior / ".env").write_text(
                "ANTHROPIC_API_KEY=sk-ant-api03-DELAANTERIOR\n", encoding="utf-8")
            (recien / "app").mkdir(parents=True)
            (recien / "data" / "imports").mkdir(parents=True)

            personal2 = tmp / "MisDocumentos2" / "ProLegends"
            cfg2.BASE_DIR = recien
            cfg2.DATA_DIR_ANTIGUA = recien / "data"
            cfg2.DATA_DIR = personal2
            cfg2.IMPORTS_DIR = personal2 / "imports"
            cfg2.DB_DIR = personal2 / "db"
            cfg2.DB_PATH = personal2 / "db" / "prolegends.db"
            os.environ["PROLEGENDS_HOME"] = str(personal2)
            casa_real = mudanza.Path.home
            mudanza.Path.home = staticmethod(lambda: tmp)
            try:
                mudanza.migrar(log=lambda m: None)
                rescatada = personal2 / "cronicas" / "Momuzosith" / "figura-7.md"
                comprobar(rescatada.exists() and "Ngôrdax" in rescatada.read_text(encoding="utf-8"),
                          "al descomprimir la versión nueva EN OTRA CARPETA, "
                          "las crónicas de la anterior se rescatan igual")
                comprobar("DELAANTERIOR" in (personal2 / ".env").read_text(encoding="utf-8"),
                          "y la clave de la API con ellas")
                comprobar((anterior / "data" / "cronicas" / "Momuzosith" / "figura-7.md").exists(),
                          "sin tocar las de la carpeta anterior")
                comprobar(recien.resolve() not in
                          [c.resolve() for c in mudanza.instalaciones_anteriores()],
                          "la copia que se está ejecutando no se busca a sí misma")
            finally:
                mudanza.Path.home = casa_real
        finally:
            (cfg2.BASE_DIR, cfg2.DATA_DIR_ANTIGUA, cfg2.DATA_DIR, cfg2.IMPORTS_DIR,
             cfg2.DB_DIR, cfg2.DB_PATH) = guardado[:6]
            if guardado[6] is None:
                os.environ.pop("PROLEGENDS_HOME", None)
            else:
                os.environ["PROLEGENDS_HOME"] = guardado[6]

        print("\n17. El mapa se dibuja con los datos, sin ficheros del jugador")
        from app.model import terreno as terr  # noqa: E402

        comprobar(terr.parse_coords("3,4|5,6|7,8") == [(3, 4), (5, 6), (7, 8)],
                  "las coordenadas se leen separadas por barras, como las escribe DFHack")

        # LA trampa: el recorrido de un rio no trae dos numeros por punto sino
        # cinco (x, y, caudal, salida, altura). Leyendo pares sueltos a lo
        # largo del texto salian coordenadas que no existen —(0,6), (60,2)—, y
        # eso llenaba el mapa de rayas de punta a punta.
        CAMINO = "4,32,0,6,117|3,32,60,2,101|3,31,124,7,101|2,31,192,8,99|"
        comprobar(terr.parse_coords(CAMINO) == [(4, 32), (3, 32), (3, 31), (2, 31)],
                  "de un recorrido de rio salen SOLO sus casillas, no los otros números")
        comprobar([len(g) for g in terr.parse_grupos(CAMINO)] == [5, 5, 5, 5],
                  "y cada punto conserva sus cinco datos")
        comprobar([g[2] for g in terr.parse_grupos(CAMINO)] == [0, 60, 124, 192],
                  "el caudal se lee y crece río abajo")
        comprobar(terr.parse_coords("1,2 3,4\n5,6") == [(1, 2), (3, 4), (5, 6)],
                  "y también separadas por espacios o saltos de línea")
        comprobar(terr.parse_coords(["9,9", "8,8"]) == [(9, 9), (8, 8)],
                  "y repartidas en varias etiquetas")
        comprobar(terr.parse_coords(None) == [] and terr.parse_coords(True) == [],
                  "y si no hay nada, no se inventa una casilla")

        geo_dir = tmp / "geografia"
        generar(geo_dir, "--mundo", "mundogeo", "--token", "regionG", "--solo-uno",
                "--anyo-final", "80", "--tam", "48", "--sitios", "40",
                "--figuras", "200", "--eventos", "900")
        conn7 = dbmod.connect(tmp / "geo.db")
        dbmod.init_db(conn7)
        import_all(conn7, imports_dir=geo_dir, verbose=False, log=lambda m: None)
        eid = dbmod.one(conn7, "SELECT id FROM exports WHERE status = 'ok'")["id"]
        mapa_geo = terr.terreno(conn7, eid)

        comprobar(mapa_geo["hay_mapa"], "hay mapa dibujable a partir del export")
        comprobar(mapa_geo["ancho"] == 48 and mapa_geo["alto"] == 48,
                  f"el mundo mide lo que dicen las regiones: {mapa_geo['ancho']}x{mapa_geo['alto']}")
        comprobar(len(mapa_geo["rejilla"]) == 48 * 48,
                  "la rejilla trae una casilla por cada punto del mundo")
        comprobar(mapa_geo["rejilla"].count(".") == 0,
                  "sin huecos: las regiones cubren el mundo entero, así que la costa es exacta")
        comprobar(any("cean" in b for b in mapa_geo["biomas"]),
                  f"se distingue el mar de la tierra: {mapa_geo['biomas'][:4]}")
        comprobar(len(mapa_geo["rios"]) > 0 and len(mapa_geo["rios"][0]["camino"]) > 2,
                  "los ríos llegan con su recorrido")
        comprobar(mapa_geo["caudal_maximo"] > 0 and mapa_geo["rios"][0]["caudal"],
                  "y con su caudal, que es lo que separa un río de un arroyo")
        comprobar(mapa_geo["rios"] == sorted(mapa_geo["rios"],
                                             key=lambda r: (r["caudal"] or 0), reverse=True),
                  "vienen ordenados del más caudaloso al menos")
        fuera = [c for r in mapa_geo["rios"] for c in r["camino"]
                 if not (0 <= c[0] < mapa_geo["ancho"] and 0 <= c[1] < mapa_geo["alto"])]
        comprobar(not fuera,
                  f"ninguna casilla de río cae fuera del mundo ({len(fuera)} sueltas)")
        saltos = sum(1 for r in mapa_geo["rios"] for i in range(1, len(r["camino"]))
                     if max(abs(r["camino"][i][0] - r["camino"][i - 1][0]),
                            abs(r["camino"][i][1] - r["camino"][i - 1][1])) > 1)
        comprobar(saltos == 0,
                  f"y ningún río salta de una punta del mapa a otra ({saltos} saltos)")
        comprobar(len(mapa_geo["construcciones"]) > 0,
                  "y las calzadas, puentes y túneles con el suyo")
        comprobar(len(mapa_geo["picos"]) > 0 and mapa_geo["picos"][0]["nombre"],
                  "los picos con nombre traen sus coordenadas")

        # El tamaño guardado tiene que cuadrar con el del mapa, o los pueblos
        # saldrían flotando fuera de su tierra.
        exp_geo = dbmod.one(conn7, "SELECT world_width, world_height FROM exports WHERE id = ?", (eid,))
        comprobar((exp_geo["world_width"], exp_geo["world_height"]) == (48, 48),
                  f"y el tamaño guardado coincide: {exp_geo['world_width']}x{exp_geo['world_height']}")

        # Sin el _plus no hay coordenadas: no se dibuja una costa inventada.
        solo_principal = tmp / "solo-principal"
        solo_principal.mkdir()
        for xml in geo_dir.glob("*-legends.xml"):
            shutil.copy2(xml, solo_principal / xml.name)
        conn8 = dbmod.connect(tmp / "solo.db")
        dbmod.init_db(conn8)
        import_all(conn8, imports_dir=solo_principal, verbose=False, log=lambda m: None)
        eid8 = dbmod.one(conn8, "SELECT id FROM exports WHERE status = 'ok'")["id"]
        pelado = terr.terreno(conn8, eid8)
        comprobar(not pelado["hay_mapa"] and pelado["motivo"],
                  "sin el _plus se dice que no hay mapa, en vez de inventarse la geografía")
        comprobar(pelado["rios"] == [] and pelado["construcciones"] == [],
                  "y no aparecen ríos ni calzadas de la nada")
        comprobar(len(pelado["regiones"]) > 0,
                  "aunque los nombres de las regiones sí se conservan")
        conn7.close()
        conn8.close()

        # El dibujo del mapa vive en JavaScript, y ahi estaba el fallo que se
        # vio con un mundo real: los rios no vienen como un recorrido ordenado
        # sino como "las casillas que ocupa esto". Unirlas por orden de lista
        # trazaba rayas de punta a punta del mundo. Se comprueba con node si
        # esta instalado; si no, se dice y se sigue.
        guion = """
global.document = { createElement: () => ({ getContext: () => ({}) }) };
%s
const salida = [];
const di = (ok, txt) => salida.push((ok ? 'OK|' : 'NO|') + txt);

// 1) Un rio dado como conjunto desordenado de casillas contiguas: una cadena.
const sueltas = [[5,3],[3,1],[4,2],[5,4],[6,4],[3,0],[4,1]];
const c1 = Atlas.cadenas(sueltas, 30, 30);
di(c1.length === 1 && c1[0].length === sueltas.length,
   'un rio desordenado se reconstruye como una sola cadena');

// 2) Nada de unir lo que no se toca: dos brazos separados, dos cadenas.
const dos = [[1,1],[2,1],[3,1],[20,20],[21,20],[22,20]];
const c2 = Atlas.cadenas(dos, 30, 30);
di(c2.length === 2, 'dos tramos separados NO se unen con una raya (' + c2.length + ')');

// 3) Cada salto de una cadena es a una casilla pegada: sin rayas largas.
let maximo = 0;
for (const cadena of c1.concat(c2)) {
  for (let i = 1; i < cadena.length; i++) {
    maximo = Math.max(maximo,
      Math.abs(cadena[i][0]-cadena[i-1][0]), Math.abs(cadena[i][1]-cadena[i-1][1]));
  }
}
di(maximo <= 1, 'ningun tramo salta mas de una casilla (maximo ' + maximo + ')');

// 4) Lo que cae fuera del mundo se descarta en vez de salirse del marco.
const fuera = Atlas.cadenas([[1,1],[2,1],[999,999],[-4,7]], 30, 30);
di(fuera.length === 1 && fuera[0].length === 2,
   'las coordenadas fuera del mundo se descartan');

// 5) Un recorrido ya ordenado sigue saliendo entero.
const recto = [];
for (let i = 0; i < 12; i++) recto.push([i, 5]);
const c5 = Atlas.cadenas(recto, 30, 30);
di(c5.length === 1 && c5[0].length === 12, 'un recorrido ya ordenado sale entero');

console.log(salida.join('\\n'));
""" % (RAIZ / "web" / "js" / "atlas.js").read_text(encoding="utf-8")

        try:
            hecho = subprocess.run(["node", "-e", guion], capture_output=True,
                                   text=True, timeout=60)
            if hecho.returncode != 0:
                comprobar(False, f"el dibujo del mapa no se ha podido comprobar: {hecho.stderr[:200]}")
            else:
                for linea in hecho.stdout.strip().splitlines():
                    estado, _, texto = linea.partition("|")
                    comprobar(estado == "OK", texto)
        except (OSError, subprocess.SubprocessError):
            print("  [  --  ] sin node instalado: no se comprueba el dibujo del mapa")

        # Y el generador tiene que producir esa misma forma, o la proxima vez
        # volveriamos a probar contra un caso mas facil que el real.
        import json as _json  # noqa: E402

        crudo = dbmod.one(
            conn7 if False else dbmod.connect(tmp / "geo.db"),
            "SELECT data_json FROM raw_records WHERE section = 'rivers' LIMIT 1",
        )
        if crudo:
            camino = _json.loads(crudo["data_json"]).get("path")
            grupos = terr.parse_grupos(camino)
            comprobar(grupos and all(len(g) == 5 for g in grupos),
                      "el export de prueba escribe los ríos con sus cinco datos por punto, "
                      "como los de verdad, y no con dos")
            alturas = [g[4] for g in grupos]
            comprobar(alturas == sorted(alturas, reverse=True),
                      "y con la altura bajando río abajo, que es como se sabe hacia dónde corre")

        print("\n18. Los sucesos se cuentan en castellano")
        from app.model import diccionario as DIC  # noqa: E402
        from app.model.narrador import Narrador, PLANTILLAS, cobertura  # noqa: E402

        cob = cobertura()
        comprobar(cob["con_plantilla"] >= 100,
                  f"hay plantilla para {cob['con_plantilla']} tipos de suceso")
        comprobar(cob["terminos"] >= 300,
                  f"el diccionario tiene {cob['terminos']} términos")

        nombres = {
            "hf": {105: "Iden Craftshailed", 121: "Uthhkos Lusbomith"},
            "sitio": {7: "Kolluslan"},
            "entidad": {1: "The Orbom of Zasuth", 2: "The Ngomuz of Onoloth"},
            "artefacto": {3: "Puñal de Zasuth"}, "estructura": {}, "region": {},
        }

        def frase(fila, datos=None):
            from app.model.narrador import Contexto, generica
            c = Contexto(fila, datos or {}, nombres)
            plantilla = PLANTILLAS.get(c.tipo)
            return plantilla(c) if plantilla else generica(c)

        dicho = frase({"year": 159, "type": "hf died", "hfid": 105,
                       "slayer_hfid": 121, "site_id": 7}, {"cause": "STRUCK"})
        comprobar(dicho == "Iden Craftshailed murió por un golpe a manos de "
                           "Uthhkos Lusbomith en Kolluslan.",
                  f"una muerte se cuenta entera: «{dicho}»")

        # Un dato ausente no se rellena con nada.
        pelada = frase({"year": 3, "type": "hf died", "hfid": 105}, {})
        comprobar(pelada == "Iden Craftshailed murió.",
                  f"y sin causa ni lugar, no se inventan: «{pelada}»")

        # Una muerte natural con un matador en el dato no se cuenta como crimen.
        vejez = frase({"year": 80, "type": "hf died", "hfid": 105, "slayer_hfid": 121},
                      {"cause": "OLD_AGE"})
        comprobar("a manos de" not in vejez,
                  f"morir de vejez no es morir a manos de nadie: «{vejez}»")

        # Un tipo desconocido no desaparece: se cuenta como se puede.
        rara = frase({"year": 9, "type": "algo que no conozco", "hfid": 105, "site_id": 7}, {})
        comprobar("Iden Craftshailed" in rara and "Kolluslan" in rara and rara.endswith("."),
                  f"un suceso sin plantilla se sigue contando: «{rara}»")

        # Ninguna plantilla puede tumbar una ficha, ni con datos absurdos.
        rotas = 0
        for tipo in PLANTILLAS:
            try:
                salida = frase({"year": None, "type": tipo}, {})
                if not isinstance(salida, str) or not salida.strip():
                    rotas += 1
            except Exception:
                rotas += 1
        comprobar(rotas == 0,
                  f"las {len(PLANTILLAS)} plantillas aguantan un evento vacío ({rotas} fallan)")

        # El diccionario nunca esconde un término: si no lo conoce, lo enseña.
        comprobar(DIC.sitio("dark fortress") == "fortaleza oscura",
                  "los términos conocidos se traducen")
        comprobar(DIC.sitio("BICHO_RARO") == "Bicho raro",
                  "y los desconocidos se enseñan limpios, no se ocultan")
        comprobar(DIC.muerte("OLD_AGE") == "de vejez" and DIC.cargo("MONARCH") == "monarca",
                  "causas de muerte y cargos también")

        # Y sobre datos de verdad, salidos de un export importado.
        filas_ev = [dict(r) for r in conn.execute(
            """SELECT event_id, year, type, site_id, civ_id, hfid, slayer_hfid,
                      attacker_civ_id, defender_civ_id, artifact_id, structure_id,
                      subregion_id, data_json
                 FROM events WHERE export_id = 1 LIMIT 400""")]
        if filas_ev:
            narrador = Narrador(conn, 1)
            frases = narrador.narrar(filas_ev)
            comprobar(all(f and f.endswith(".") for f in frases),
                      f"las {len(frases)} frases de un export real salen completas")
            comprobar(not any("None" in f or "hfid" in f for f in frases),
                      "y ninguna se cuela con identificadores o huecos vacíos")
            con_nombre = sum(1 for f in frases if any(c.isupper() for c in f[1:]))
            comprobar(con_nombre > len(frases) * 0.5,
                      f"la mayoría nombran a alguien o algo ({con_nombre} de {len(frases)})")

        conn.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------ 19
    print()
    print("19. Cada mundo llama a las cosas a su manera")
    from app.model.narrador import (ALIAS_TIPOS, normalizar_tipo,  # noqa: E402
                                    plantilla_de, variantes)

    # Un mismo suceso viene escrito de varias formas segun el export. Todas
    # tienen que acabar en la misma plantilla, o la ficha se llena de frases
    # genericas sin que nadie se entere.
    comprobar(normalizar_tipo("hist figure died") == "hf died"
              and normalizar_tipo("hist_figure_died") == "hf died"
              and normalizar_tipo("HF DIED") == "hf died",
              "'hist figure died', 'hist_figure_died' y 'HF DIED' son la misma muerte")
    comprobar(plantilla_de("change_hf_state") is not None
              and plantilla_de("CREATED_SITE") is not None,
              "los guiones bajos y las mayusculas no dejan sin frase a un suceso")
    comprobar(all(plantilla_de(destino) is not None for destino in ALIAS_TIPOS.values()),
              f"los {len(ALIAS_TIPOS)} alias apuntan a una plantilla que existe")
    comprobar("hist figure died" in variantes("hf died")
              and "hf_died" in variantes("hf died"),
              "las consultas a la base de datos preguntan por todas las formas")

    # Las razas se leen en castellano, pero el codigo interno no se toca: es lo
    # que usan los filtros y los colores.
    comprobar(DIC.raza("DWARF") == "enano" and DIC.raza("elf") == "elfo",
              "las razas comunes se leen en castellano")
    comprobar(DIC.raza("GIANT_CAVE_SPIDER") == "araña gigante de las cavernas",
              "y los codigos con guion bajo tambien se reconocen")
    comprobar(DIC.raza("BLENDEC") == "Blendec",
              "una criatura que no esta en el diccionario se enseña limpia, no se inventa")

    # Las casillas de "ver el dato en bruto" se quitaron: que no vuelvan.
    ui = (RAIZ / "web" / "js" / "ui.js").read_text(encoding="utf-8")
    comprobar("interruptorBruto" not in ui and "verCrudo" not in ui,
              "ya no hay casillas de 'ver el dato en bruto' por las fichas")

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
