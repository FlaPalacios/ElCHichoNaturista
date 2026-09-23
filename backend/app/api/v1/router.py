"""Agrupa las rutas de la versión 1 de la API.

Catálogo (lectura), pedidos, ubigeo, envío y el panel de administración.
"""

from fastapi import APIRouter

from app.api.v1 import (
    categorias,
    envio,
    marcas,
    pedidos,
    productos,
    tienda,
    ubigeo,
)
from app.api.v1.admin import router as admin

router = APIRouter()
router.include_router(categorias.router)
router.include_router(marcas.router)
router.include_router(productos.router)
router.include_router(pedidos.router)
router.include_router(ubigeo.router)
router.include_router(envio.router)
router.include_router(tienda.router)
router.include_router(admin.router)
