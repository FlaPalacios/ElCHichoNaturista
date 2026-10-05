"""Pedidos vistos desde el panel: listar, ver, cambiar estado y anotar."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud
from app import tienda as ajustes_tienda
from app.database import obtener_sesion
from app.models import Admin, EstadoPedido
from app.schemas import PedidoAdminOut
from app.seguridad import admin_actual

router = APIRouter(prefix="/pedidos", tags=["admin"])


class CambioEstado(BaseModel):
    estado: EstadoPedido
    # Al pasar a "enviado" se piden en la misma llamada, para no hacer dos.
    courier: str | None = Field(default=None, max_length=100)
    codigo_seguimiento: str | None = Field(default=None, max_length=100)


class NotaInterna(BaseModel):
    nota_interna: str | None = Field(default=None, max_length=2000)


def _buscar(sesion: Session, numero_pedido: str):
    pedido = crud.obtener_pedido_por_numero(sesion, numero_pedido)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el pedido '{numero_pedido}'.",
        )
    return pedido


@router.get(
    "",
    response_model=list[PedidoAdminOut],
    summary="Lista los pedidos con filtros",
)
def listar_pedidos(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    estado: Annotated[EstadoPedido | None, Query()] = None,
    desde: Annotated[date | None, Query(description="Fecha inicial, inclusive.")] = None,
    hasta: Annotated[date | None, Query(description="Fecha final, inclusive.")] = None,
    q: Annotated[
        str | None,
        Query(max_length=100, description="Número de pedido, teléfono o nombre."),
    ] = None,
):
    return crud.listar_pedidos(sesion, estado=estado, desde=desde, hasta=hasta, q=q)


@router.get(
    "/{numero_pedido}",
    response_model=PedidoAdminOut,
    summary="Detalle de un pedido",
    responses={404: {"description": "No existe ese pedido"}},
)
def obtener_pedido(
    numero_pedido: str,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    return _buscar(sesion, numero_pedido)


@router.patch(
    "/{numero_pedido}/estado",
    response_model=PedidoAdminOut,
    summary="Cambia el estado del pedido",
    responses={
        404: {"description": "No existe ese pedido"},
        422: {"description": "No hay stock para confirmar el pedido"},
    },
)
def cambiar_estado(
    numero_pedido: str,
    cambio: CambioEstado,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """Al pasar a `pago_confirmado` se descuenta el stock; si después se
    cancela o queda sin concretar, vuelve."""
    pedido = _buscar(sesion, numero_pedido)

    if cambio.courier is not None:
        pedido.courier = cambio.courier
    if cambio.codigo_seguimiento is not None:
        pedido.codigo_seguimiento = cambio.codigo_seguimiento

    try:
        crud.cambiar_estado(
            sesion,
            pedido,
            cambio.estado,
            vender_sin_stock=not ajustes_tienda.si_no(sesion, "mostrar_agotado"),
        )
    except crud.StockInsuficiente as error:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    sesion.commit()
    return crud.obtener_pedido_por_numero(sesion, numero_pedido)


@router.patch(
    "/{numero_pedido}/nota",
    response_model=PedidoAdminOut,
    summary="Guarda la nota interna del pedido",
    responses={404: {"description": "No existe ese pedido"}},
)
def guardar_nota(
    numero_pedido: str,
    nota: NotaInterna,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    pedido = _buscar(sesion, numero_pedido)
    pedido.nota_interna = nota.nota_interna
    sesion.commit()
    return crud.obtener_pedido_por_numero(sesion, numero_pedido)
