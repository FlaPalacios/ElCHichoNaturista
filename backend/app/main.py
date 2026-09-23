"""Punto de entrada de la API.

    uvicorn app.main:app --reload
"""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import router as router_v1
from app.config import ajustes
from app.database import obtener_sesion
from app.schemas import Salud

# En el servidor la documentación queda cerrada: lista todas las rutas del
# panel y facilita tantear la API desde fuera. En desarrollo sigue en /docs.
_en_servidor = ajustes.entorno.lower() in {"produccion", "producción", "production"}

app = FastAPI(
    title=ajustes.proyecto,
    version=ajustes.version,
    description="API de la tienda El Chico Naturista.",
    docs_url=None if _en_servidor else "/docs",
    redoc_url=None if _en_servidor else "/redoc",
    openapi_url=None if _en_servidor else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ajustes.origenes_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router_v1, prefix=ajustes.prefijo_api)


@app.get("/", tags=["estado"], summary="Datos básicos de la API")
def raiz():
    return {
        "proyecto": ajustes.proyecto,
        "version": ajustes.version,
        "docs": None if _en_servidor else "/docs",
        "api": ajustes.prefijo_api,
    }


@app.get(
    f"{ajustes.prefijo_api}/salud",
    response_model=Salud,
    tags=["estado"],
    summary="Comprueba que la API y la base de datos responden",
)
def salud(sesion: Annotated[Session, Depends(obtener_sesion)]):
    try:
        sesion.execute(text("SELECT 1"))
        base = "conectada"
    except Exception as error:  # pragma: no cover - solo para diagnóstico
        base = f"error: {error.__class__.__name__}"
    return Salud(estado="ok", base_de_datos=base, version=ajustes.version)
