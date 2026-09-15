"""Agrupa las rutas de la versión 1 de la API.

Etapa 3: solo lectura de catálogo. Los routers de pedidos (etapa 5) y
administración (etapa 6) se enganchan aquí cuando toque.
"""

from fastapi import APIRouter

from app.api.v1 import categorias, productos

router = APIRouter()
router.include_router(categorias.router)
router.include_router(productos.router)
