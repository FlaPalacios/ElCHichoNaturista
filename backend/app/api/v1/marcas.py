"""GET /api/v1/marcas"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.database import obtener_sesion
from app.schemas import Breve

router = APIRouter(prefix="/marcas", tags=["marcas"])


@router.get(
    "",
    response_model=list[Breve],
    summary="Lista las marcas con productos a la venta",
)
def listar_marcas(sesion: Annotated[Session, Depends(obtener_sesion)]):
    return crud.listar_marcas(sesion)
