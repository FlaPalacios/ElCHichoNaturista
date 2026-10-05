"""POST /api/v1/pedidos y GET /api/v1/pedidos/{numero_pedido}"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app import tienda as ajustes_tienda
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
    try:
        pedido = crud.crear_pedido(
            sesion,
            nombre_contacto=payload.nombre_contacto,
            telefono_contacto=payload.telefono_contacto,
            correo=payload.correo,
            direccion=payload.direccion,
            ubigeo=payload.ubigeo,
            referencia=payload.referencia,
            nota=payload.nota,
            items=[(i.producto_id, i.cantidad) for i in payload.items],
            envio_gratis_desde=ajustes_tienda.numero(sesion, "envio_gratis_desde"),
            vender_sin_stock=not ajustes_tienda.si_no(sesion, "mostrar_agotado"),
        )
    except (
        crud.ProductoNoDisponible,
        crud.StockInsuficiente,
        crud.DestinoNoValido,
    ) as error:
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
