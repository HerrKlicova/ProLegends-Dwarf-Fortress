"""Servidor web de ProLegends.

Sirve la API interna en /api y la interfaz estatica en /. No hay ningun paso de
compilacion: la interfaz es HTML, CSS y JavaScript sin mas.
"""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from . import config, db as dbmod
from .api import router as api_router
from .errors import ProLegendsError

app = FastAPI(
    title="ProLegends",
    description="Explorador local del archivo de leyendas de Dwarf Fortress",
    version="1.3.1",
    docs_url="/api/docs",
    redoc_url=None,
)


@app.on_event("startup")
def _preparar() -> None:
    from . import mudanza

    mudanza.migrar(log=print)
    config.ensure_dirs()
    conn = dbmod.connect()
    try:
        dbmod.init_db(conn)
        # Las versiones anteriores a la 1.2.0 guardaban las crónicas dentro de la
        # base de datos. Se sacan a fichero para que no se pierdan.
        from .ai import almacen

        rescatadas = almacen.migrar_desde_bd(conn)
        if rescatadas:
            print(f"  {rescatadas} crónica(s) guardadas ya en data/cronicas/")
    finally:
        conn.close()


@app.exception_handler(ProLegendsError)
def _error_controlado(request: Request, exc: ProLegendsError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(sqlite3.Error)
def _error_sqlite(request: Request, exc: sqlite3.Error):
    return JSONResponse(
        status_code=500,
        content={
            "error": "La base de datos ha dado un error.",
            "detalle": f"{exc}. Si el problema sigue, ejecuta 'python -m app.cli reiniciar-bd' "
                       "y vuelve a importar.",
        },
    )


@app.exception_handler(Exception)
def _error_inesperado(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Ha ocurrido un error inesperado en el servidor.",
            "detalle": str(exc),
        },
    )


app.include_router(api_router)


@app.get("/salud")
def salud():
    return {"estado": "ok", "version": app.version}


class InterfazSiempreFresca(StaticFiles):
    """Sirve la interfaz obligando al navegador a preguntar si ha cambiado.

    Sin esto, el navegador se queda con el HTML y el JavaScript de la versión
    anterior: como la dirección es siempre la misma (127.0.0.1), al actualizar
    ProLegends seguías viendo la interfaz vieja hasta que caducase la caché.
    Con 'no-cache' el navegador sigue guardándolo, pero pregunta antes de
    usarlo; si no ha cambiado, el servidor responde "sigue igual" y no se
    transfiere nada. En local eso no cuesta nada.
    """

    def file_response(self, *args, **kwargs) -> Response:
        respuesta = super().file_response(*args, **kwargs)
        respuesta.headers["Cache-Control"] = "no-cache, must-revalidate"
        return respuesta


config.ensure_dirs()
app.mount("/", InterfazSiempreFresca(directory=str(config.WEB_DIR), html=True), name="web")
