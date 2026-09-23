"""Rutas del panel. Todas menos el login exigen un token válido."""

from fastapi import APIRouter

from app.api.v1.admin import (
    auth,
    clasificacion,
    configuracion,
    pedidos,
    productos,
    resumen,
)

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(pedidos.router)
router.include_router(productos.router)
router.include_router(clasificacion.router)
router.include_router(resumen.router)
router.include_router(configuracion.router)
