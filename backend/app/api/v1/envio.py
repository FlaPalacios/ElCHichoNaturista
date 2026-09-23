"""GET /api/v1/envio — cuánto cuesta enviar a un distrito.

El checkout lo consulta al elegir el distrito, para mostrar el costo antes de
confirmar. Quien manda sigue siendo `POST /pedidos`, que lo vuelve a calcular.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app import tienda as ajustes_tienda
from app.database import obtener_sesion

router = APIRouter(prefix="/envio", tags=["envio"])


class EnvioOut(BaseModel):
    ubigeo: str
    departamento: str
    provincia: str
    distrito: str
    costo: Decimal
    envio_gratis_desde: Decimal


@router.get(
    "",
    response_model=EnvioOut,
    summary="Costo de envío a un distrito",
    responses={404: {"description": "No existe ese distrito"}},
)
def consultar_envio(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    ubigeo: Annotated[str, Query(min_length=6, max_length=6, examples=["150122"])],
):
    distrito = crud.obtener_distrito(sesion, ubigeo)
    if distrito is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el distrito '{ubigeo}'.",
        )

    provincia = distrito.provincia
    return EnvioOut(
        ubigeo=distrito.codigo,
        departamento=provincia.departamento.nombre,
        provincia=provincia.nombre,
        distrito=distrito.nombre,
        costo=crud.costo_envio(sesion, distrito),
        envio_gratis_desde=ajustes_tienda.numero(sesion, "envio_gratis_desde"),
    )
