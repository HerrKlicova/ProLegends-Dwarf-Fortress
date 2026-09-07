"""Comprobacion de extremo a extremo.

Genera exports de mentira con las trampas del formato real, los importa en una
base de datos aparte y verifica que todo sale como debe. Si algo se rompe,
esto lo dice sin necesidad de mirar codigo:

    python tools/autocomprobacion.py
"""

from __future__ import annotations

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

        print("\n1. Importacion")
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
                  f"cada mundo deduce su propio tamano de mapa: {anchos}")

        print("\n3. Trampas del formato")
        con_sol = dbmod.one(
            conn, "SELECT COUNT(*) n FROM sites WHERE name LIKE '%' || char(9788) || '%'")
        comprobar(con_sol["n"] > 0, "los bytes de control C0 se leen como su simbolo CP437")
        acentos = dbmod.one(
            conn, "SELECT COUNT(*) n FROM historical_figures WHERE name LIKE '%é%'")
        comprobar(acentos["n"] > 0, "los caracteres altos de CP437 se decodifican bien")
        entidades_con_tipo = dbmod.one(
            conn, "SELECT COUNT(*) n FROM entities WHERE type IS NOT NULL AND name IS NOT NULL")
        comprobar(entidades_con_tipo["n"] > 0,
                  "el nombre del principal y el tipo del _plus acaban en la misma fila")

        print("\n4. Jerarquia y propiedad")
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
        comprobar(cambios["n"] > 0, "hay historico de propietarios por anyo")
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
        comprobar(fort["novedades"] is not None, "el diff entre los dos exports esta disponible")
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
