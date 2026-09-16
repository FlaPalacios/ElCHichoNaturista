"""Agrupa las rutas de la versión 1 de la API.

Etapa 5: catálogo (lectura) y pedidos. Administración (etapa 6) falta.
"""

from fastapi import APIRouter

from app.api.v1 import categorias, pedidos, productos

router = APIRouter()
router.include_router(categorias.router)
router.include_router(productos.router)
router.include_router(pedidos.router)
