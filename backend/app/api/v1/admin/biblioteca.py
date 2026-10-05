"""La biblioteca de fotos: todo lo que hay en Cloudinary y dónde se usa."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import fotos
from app.database import obtener_sesion
from app.models import Admin, ImagenProducto, Producto
from app.seguridad import admin_actual

router = APIRouter(prefix="/fotos", tags=["admin"])


@router.get("", summary="Todas las fotos de Cloudinary y en qué productos están")
def biblioteca(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """Sirve para ver lo que ya está subido antes de subir otra vez la misma
    foto. Cada una trae los productos que la usan (vacío = sin usar)."""
    try:
        lista = fotos.listar()
    except fotos.ErrorFoto as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    nombres = dict(sesion.execute(select(Producto.codigo, Producto.nombre)).all())
    en_uso: dict[str, list[dict]] = {}
    for imagen in sesion.scalars(select(ImagenProducto)):
        clave = imagen.public_id or fotos.public_id_desde_url(imagen.url)
        if clave:
            en_uso.setdefault(clave, []).append(
                {"codigo": imagen.id_producto, "nombre": nombres.get(imagen.id_producto, "")}
            )

    return {
        "total": len(lista),
        "fotos": [
            {
                "public_id": f["public_id"],
                "url": f["secure_url"],
                "ancho": f.get("width"),
                "alto": f.get("height"),
                "peso": f.get("bytes"),
                "formato": f.get("format"),
                "subida": f.get("created_at"),
                "usada_en": en_uso.get(f["public_id"], []),
            }
            for f in lista
        ],
    }
