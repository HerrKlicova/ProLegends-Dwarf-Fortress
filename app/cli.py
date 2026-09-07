"""Linea de comandos de ProLegends.

    python -m app.cli diagnostico     dice qué ve la aplicación en cada fichero
    python -m app.cli ordenar         renombra y ordena los XML de data/imports/
    python -m app.cli importar        procesa data/imports/ y vuelca a SQLite
    python -m app.cli listar          muestra mundos y exports ya importados
    python -m app.cli servidor        arranca el servidor web
    python -m app.cli reiniciar-bd    borra la base de datos (los XML no se tocan)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, db as dbmod
from .errors import ProLegendsError


def _consola_utf8() -> None:
    """Deja la consola preparada para tildes y eñes.

    En Windows la consola puede venir en una página de códigos antigua que no
    sabe escribir 'año'. Se intenta pasar a UTF-8; si no se puede, al menos se
    sustituye el carácter problemático por '?' en lugar de reventar.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_consola_utf8()


def cmd_importar(args: argparse.Namespace) -> int:
    from .parser.importer import import_all

    with dbmod.session() as conn:
        print(f"Buscando exports en {config.IMPORTS_DIR}")
        resultado = import_all(
            conn,
            imports_dir=config.IMPORTS_DIR,
            verbose=not args.silencioso,
            only_prefix=args.prefijo,
        )
    print("\nResumen:")
    print(f"  importados: {len(resultado['importados'])}")
    print(f"  ya estában: {len(resultado['omitidos'])}")
    print(f"  con error : {len(resultado['errores'])}")
    for err in resultado["errores"]:
        print(f"    - {err['prefix']}: {err['error']}")
    return 1 if resultado["errores"] else 0


def cmd_ordenar(args: argparse.Namespace) -> int:
    from .parser import organizer

    with dbmod.session() as conn:
        grupos, avisos = organizer.planificar(
            config.IMPORTS_DIR, en_carpetas=not args.sin_carpetas, conn=conn
        )
        for aviso in avisos:
            print(f"  [aviso] {aviso}")

        pendientes = [g for g in grupos if g.cambia]
        if not pendientes:
            if grupos:
                print("  Todo está ya ordenado, no hay nada que renombrar.")
            else:
                print(f"  No hay ningún export en {config.IMPORTS_DIR}.")
            return 0

        print(f"\n  Se van a reorganizar {len(pendientes)} export(s):\n")
        for grupo in pendientes:
            cabecera = grupo.mundo or "mundo desconocido"
            if grupo.fecha:
                cabecera += f"  (año {grupo.fecha[0]})"
            print(f"  # {cabecera}")
            for mov in grupo.movimientos:
                if mov.cambia:
                    destino = mov.destino.relative_to(config.IMPORTS_DIR)
                    print(f"      {mov.origen.name}\n        -> {destino}")
            if grupo.aviso:
                print(f"      nota: {grupo.aviso}")
            print()

        if not args.aplicar:
            print("  Esto es solo una vista previa. Para hacerlo de verdad:")
            print("      python -m app.cli ordenar --aplicar")
            return 0

        resultado = organizer.aplicar(pendientes, conn=conn, log=lambda m: None)
        print(f"  Listo: {len(resultado['movidos'])} fichero(s) reorganizado(s).")
        for fallo in resultado["fallos"]:
            print(f"  [ERROR] {fallo}")
        return 1 if resultado["fallos"] else 0


def cmd_diagnostico(_: argparse.Namespace) -> int:
    """Vuelca lo que la aplicación entiende de cada fichero.

    Sirve para pegar el resultado y averiguar qué pasa sin tener que mover
    ficheros de 45 MB de un sitio a otro.
    """
    from .parser import organizer
    from .parser.discover import discover

    estado = config.diagnostico_clave()
    print("Configuración de la clave de la API:")
    print(f"      fichero:            {estado['ruta']}")
    print(f"      ¿existe?            {'sí' if estado['existe'] else 'NO'}")
    if estado["existe"]:
        print(f"      ocupa:              {estado['tamano']} caracteres")
        print(f"      guardado por última vez: {estado['modificado']}")
    if estado["fallo_lectura"]:
        print(f"      problema al leerlo: {estado['fallo_lectura']}")
    if estado["mal_nombrados"]:
        print(f"      OJO, sobra:         {', '.join(estado['mal_nombrados'])}")
    if estado["tiene_clave"]:
        clave = estado["clave"]
        print(f"      clave encontrada:   {clave[:12]}...{clave[-4:]}  ({len(clave)} caracteres)")
        if estado["formato_raro"]:
            print("      OJO: no empieza por 'sk-ant-'")
    else:
        print("      clave encontrada:   NINGUNA")
        print(f"      ¿está la línea?     {'sí, pero vacía' if estado['linea_presente'] else 'no'}")
    print(f"      modelo:             {config.modelo_ia()}")

    print(f"\nCarpeta: {config.IMPORTS_DIR}")
    ficheros = sorted(config.IMPORTS_DIR.rglob("*.xml"))
    if not ficheros:
        print("  (no hay ningún .xml)")
    for ruta in ficheros:
        tam = ruta.stat().st_size / 1048576
        cabecera = organizer.leer_cabecera(ruta)
        print(f"\n  {ruta.relative_to(config.IMPORTS_DIR)}   ({tam:.1f} MB)")
        print(f"      ¿es un export de leyendas?  {'sí' if cabecera['es_legends'] else 'NO'}")
        print(f"      nombre del mundo:           {cabecera['nombre']!r}")
        print(f"      nombre alternativo:         {cabecera['altnombre']!r}")
        if cabecera["error"]:
            print(f"      error al leerlo:            {cabecera['error']}")

    print("\nParejas que se han reconocido:")
    pares, avisos = discover(config.IMPORTS_DIR)
    if not pares:
        print("  (ninguna)")
    for par in pares:
        print(f"  - {par.prefix}   (año {par.game_year})")
        print(f"      principal: {par.main.name if par.main else 'FALTA'}")
        print(f"      plus:      {par.plus.name if par.plus else 'FALTA'}")
    for aviso in avisos:
        print(f"  [aviso] {aviso}")

    with dbmod.session() as conn:
        print("\nMundos ya guardados en la base de datos:")
        mundos = dbmod.all_(conn, "SELECT id, name, altname FROM worlds ORDER BY name")
        if not mundos:
            print("  (ninguno)")
        for mundo in mundos:
            exports = dbmod.all_(
                conn,
                "SELECT prefix, status FROM exports WHERE world_id = ? ORDER BY id",
                (mundo["id"],),
            )
            print(f"  - {mundo['name']!r}  (alt: {mundo['altname']!r})")
            for exp in exports:
                print(f"      export {exp['prefix']}  [{exp['status']}]")
        sueltos = dbmod.all_(
            conn, "SELECT prefix, status, message FROM exports WHERE world_id IS NULL"
        )
        for exp in sueltos:
            print(f"  - export sin mundo: {exp['prefix']} [{exp['status']}] {exp['message']}")
    print("\nSi algo no cuadra, pega todo esto tal cual.")
    return 0


def cmd_listar(_: argparse.Namespace) -> int:
    with dbmod.session() as conn:
        mundos = dbmod.all_(conn, "SELECT * FROM worlds ORDER BY name")
        if not mundos:
            print("No hay ningún mundo importado todavía.")
            return 0
        for mundo in mundos:
            print(f"\n# {mundo['name']}" + (f"  ({mundo['altname']})" if mundo["altname"] else ""))
            for exp in dbmod.all_(
                conn,
                """SELECT prefix, game_year, status, world_width, world_height,
                          min_year, max_year, imported_at
                     FROM exports WHERE world_id = ?
                    ORDER BY game_year, game_month, game_day""",
                (mundo["id"],),
            ):
                print(
                    f"  - {exp['prefix']:<32} año {exp['game_year']}  "
                    f"mapa {exp['world_width']}x{exp['world_height']}  "
                    f"eventos {exp['min_year']}-{exp['max_year']}  [{exp['status']}]"
                )
    return 0


def cmd_servidor(args: argparse.Namespace) -> int:
    import threading
    import time
    import webbrowser

    import uvicorn

    host = args.host or config.HOST
    puerto = args.puerto or config.PORT
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{puerto}/"

    if args.abrir:
        def abrir_cuando_este_listo() -> None:
            import urllib.error
            import urllib.request

            for _ in range(90):
                try:
                    urllib.request.urlopen(url + "salud", timeout=1)
                    break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.4)
            webbrowser.open(url)

        threading.Thread(target=abrir_cuando_este_listo, daemon=True).start()

    print()
    print("=" * 64)
    print(f"  ProLegends esta funcionando en   {url}")
    print("  Deja esta ventana abierta mientras uses la aplicación.")
    print("  Para cerrarla: pulsa Ctrl+C o cierra esta ventana.")
    print("=" * 64)
    print()

    uvicorn.run(
        "app.main:app",
        host=host,
        port=puerto,
        log_level="warning",
        reload=False,
    )
    return 0


def cmd_reiniciar(_: argparse.Namespace) -> int:
    path = Path(config.DB_PATH)
    borrados = 0
    for sufijo in ("", "-wal", "-shm"):
        candidato = Path(str(path) + sufijo)
        if candidato.exists():
            candidato.unlink()
            borrados += 1
    print(f"Base de datos eliminada ({borrados} ficheros).")
    print("No se han tocado los XML de data/imports/ ni las crónicas de data/cronicas/.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prolegends", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_imp = sub.add_parser("importar", help="procesa los XML de data/imports/")
    p_imp.add_argument("--prefijo", help="importar solo este export (ej. region1-00101-07-24)")
    p_imp.add_argument("--silencioso", action="store_true", help="sin barra de progreso")
    p_imp.set_defaults(func=cmd_importar)

    p_ord = sub.add_parser(
        "ordenar",
        help="renombra los XML según el mundo y la fecha, y los reparte por carpetas",
    )
    p_ord.add_argument("--aplicar", action="store_true",
                       help="hacerlo de verdad (sin esto solo se muestra el plan)")
    p_ord.add_argument("--sin-carpetas", action="store_true", dest="sin_carpetas",
                       help="renombrar pero dejarlo todo en data/imports/")
    p_ord.set_defaults(func=cmd_ordenar)

    p_diag = sub.add_parser(
        "diagnostico", help="dice qué ve la aplicación en cada fichero de data/imports/"
    )
    p_diag.set_defaults(func=cmd_diagnostico)

    p_lst = sub.add_parser("listar", help="mundos y exports ya importados")
    p_lst.set_defaults(func=cmd_listar)

    p_srv = sub.add_parser("servidor", help="arranca el servidor web")
    p_srv.add_argument("--host")
    p_srv.add_argument("--puerto", type=int)
    p_srv.add_argument("--abrir", action="store_true", help="abre el navegador solo")
    p_srv.set_defaults(func=cmd_servidor)

    p_res = sub.add_parser(
        "reiniciar-bd",
        help="borra la base de datos generada (las crónicas NO se tocan)",
    )
    p_res.set_defaults(func=cmd_reiniciar)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ProLegendsError as exc:
        print(f"\nERROR: {exc.message}", file=sys.stderr)
        if exc.detail:
            print(f"       {exc.detail}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
