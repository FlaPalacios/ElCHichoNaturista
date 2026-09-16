"""POST /api/v1/pedidos y GET /api/v1/pedidos/{numero_pedido}"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.config import ajustes
from app.database import obtener_sesion
from app.schemas import PedidoCrear, PedidoOut

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


@router.post(
    "",
    response_model=PedidoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un pedido con sus items",
)
def crear_pedido(payload: PedidoCrear, sesion: Annotated[Session, Depends(obtener_sesion)]):
    """Recalcula precios y envío desde la base: nunca confía en lo que manda el cliente."""
    if payload.entrega == "delivery" and (not payload.direccion or not payload.distrito):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Para delivery hace falta dirección y distrito.",
        )

    try:
        pedido = crud.crear_pedido(
            sesion,
            nombre_contacto=payload.nombre_contacto,
            telefono_contacto=payload.telefono_contacto,
            correo=payload.correo,
            entrega=payload.entrega,
            direccion=payload.direccion,
            distrito=payload.distrito,
            referencia=payload.referencia,
            metodo_pago=payload.metodo_pago,
            nota=payload.nota,
            items=[(i.producto_id, i.cantidad) for i in payload.items],
            costo_envio_lima=ajustes.envio_costo_lima,
            envio_gratis_desde=ajustes.envio_gratis_desde,
        )
    except (crud.ProductoNoDisponible, crud.StockInsuficiente) as error:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    sesion.commit()
    # Se relee con carga explícita (misma consulta que usa el GET) en vez de
    # sesion.refresh + lazy-load implícito: no depende del ciclo de vida de la
    # sesión tras el commit.
    return crud.obtener_pedido_por_numero(sesion, pedido.numero_pedido)


@router.get(
    "/{numero_pedido}",
    response_model=PedidoOut,
    summary="Consulta un pedido por su número",
    responses={404: {"description": "No existe un pedido con ese número"}},
)
def obtener_pedido(numero_pedido: str, sesion: Annotated[Session, Depends(obtener_sesion)]):
    """Público solo con el número, sin teléfono adicional (decisión de producto aceptada)."""
    pedido = crud.obtener_pedido_por_numero(sesion, numero_pedido)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el pedido '{numero_pedido}'.",
        )
    return pedido
