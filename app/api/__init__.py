"""API interna.

Cada vista de la interfaz habla solo con estos endpoints; nunca con el parser.
Para anadir una vista nueva basta con crear un router aqui y una pagina en web/.
"""

from fastapi import APIRouter

from . import atlas, chronicle, figures, fortress, worlds

router = APIRouter(prefix="/api")
router.include_router(worlds.router)
router.include_router(atlas.router)
router.include_router(figures.router)
router.include_router(fortress.router)
router.include_router(chronicle.router)
