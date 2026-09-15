"""GET /api/v1/categorias"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.database import obtener_sesion
from app.schemas import CategoriaOut

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.get(
    "",
    response_model=list[CategoriaOut],
    summary="Lista las categorías del catálogo",
)
def listar_categorias(sesion: Annotated[Session, Depends(obtener_sesion)]):
    """Devuelve las categorías en el orden en que deben aparecer en el menú."""
    return crud.listar_categorias(sesion)
