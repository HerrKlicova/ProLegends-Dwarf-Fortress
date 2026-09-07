"""Servidor web de ProLegends.

Sirve la API interna en /api y la interfaz estatica en /. No hay ningun paso de
compilacion: la interfaz es HTML, CSS y JavaScript sin mas.
"""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db as dbmod
from .api import router as api_router
from .errors import ProLegendsError

app = FastAPI(
    title="ProLegends",
    description="Explorador local del archivo de leyendas de Dwarf Fortress",
    version="1.0.2",
    docs_url="/api/docs",
    redoc_url=None,
)


@app.on_event("startup")
def _preparar() -> None:
    config.ensure_dirs()
    conn = dbmod.connect()
    try:
        dbmod.init_db(conn)
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


config.ensure_dirs()
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
