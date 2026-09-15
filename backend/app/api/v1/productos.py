"""GET /api/v1/productos y GET /api/v1/productos/{slug}"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import obtener_sesion
from app.schemas import ProductoOut

router = APIRouter(prefix="/productos", tags=["productos"])


@router.get(
    "",
    response_model=list[ProductoOut],
    summary="Lista productos con filtros",
)
def listar_productos(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    categoria: Annotated[
        str | None,
        Query(description="Slug de la categoría, por ejemplo `suplementos`.", max_length=100),
    ] = None,
    precio_min: Annotated[
        Decimal | None, Query(ge=0, description="Precio mínimo en soles.")
    ] = None,
    precio_max: Annotated[
        Decimal | None, Query(ge=0, description="Precio máximo en soles.")
    ] = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=100, description="Busca en nombre y descripción corta."),
    ] = None,
    destacado: Annotated[
        bool | None, Query(description="`true` devuelve solo los destacados.")
    ] = None,
    mas_vendido: Annotated[
        bool | None, Query(description="`true` devuelve solo los más vendidos.")
    ] = None,
    en_oferta: Annotated[
        bool | None,
        Query(description="`true` devuelve solo los que tienen precio anterior."),
    ] = None,
):
    """Solo devuelve productos activos: los inactivos no se muestran en la tienda."""
    if precio_min is not None and precio_max is not None and precio_min > precio_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="precio_min no puede ser mayor que precio_max.",
        )

    if categoria and crud.obtener_categoria_por_slug(sesion, categoria) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la categoría '{categoria}'.",
        )

    return crud.listar_productos(
        sesion,
        categoria=categoria,
        precio_min=precio_min,
        precio_max=precio_max,
        q=q,
        destacado=destacado,
        mas_vendido=mas_vendido,
        en_oferta=en_oferta,
    )


@router.get(
    "/{slug}",
    response_model=ProductoOut,
    summary="Detalle de un producto por slug",
    responses={404: {"description": "El producto no existe o está inactivo"}},
)
def obtener_producto(slug: str, sesion: Annotated[Session, Depends(obtener_sesion)]):
    producto = crud.obtener_producto_por_slug(sesion, slug)
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el producto '{slug}'.",
        )
    return producto
