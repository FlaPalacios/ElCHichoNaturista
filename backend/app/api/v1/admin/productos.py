"""Catálogo desde el panel: crear, editar, activar y manejar las fotos."""

import csv
import io
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app import crud, fotos
from app import importar as importar_tsv
from app import tienda as ajustes_tienda
from app.database import obtener_sesion
from app.models import Admin, ImagenProducto, Marca, Producto, Subcategoria
from app.schemas import (
    CambioActivo,
    CambioStock,
    OrdenImagenes,
    ProductoAdminOut,
    ProductoCrear,
    ProductoEntrada,
)
from app.seguridad import admin_actual

router = APIRouter(prefix="/productos", tags=["admin"])

# Mismas columnas que `app/datos/catalogo.tsv`, para que exportar e importar
# sean la misma planilla.
COLUMNAS_TSV = importar_tsv.COLUMNAS


def _buscar(sesion: Session, codigo: str) -> Producto:
    producto = crud.obtener_producto_admin(sesion, codigo)
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el producto '{codigo}'.",
        )
    return producto


def _validar_relaciones(sesion: Session, marca_id: int, subcategoria_id: int) -> None:
    marca = sesion.get(Marca, marca_id)
    if marca is None or marca.eliminado_en is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No existe la marca {marca_id}.",
        )
    sub = sesion.get(Subcategoria, subcategoria_id)
    if sub is None or sub.eliminado_en is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No existe la subcategoría {subcategoria_id}.",
        )


@router.get("", response_model=list[ProductoAdminOut], summary="Todo el catálogo")
def listar(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    categoria_id: Annotated[int | None, Query()] = None,
    subcategoria_id: Annotated[int | None, Query()] = None,
    marca_id: Annotated[int | None, Query()] = None,
    activo: Annotated[bool | None, Query()] = None,
    stock_bajo: Annotated[bool, Query(description="Solo los que están por acabarse.")] = False,
    orden: Annotated[
        str,
        Query(description="codigo, nuevos, editados, nombre, stock o precio."),
    ] = "codigo",
):
    return crud.listar_productos_admin(
        sesion,
        q=q,
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
        marca_id=marca_id,
        activo=activo,
        stock_bajo_de=ajustes_tienda.entero(sesion, "stock_bajo") if stock_bajo else None,
        orden=orden,
    )


@router.get(
    "/siguiente-codigo",
    summary="Sugiere el próximo código libre",
)
def proximo_codigo(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    return {"codigo": crud.siguiente_codigo(sesion)}


@router.get(
    "/exportar",
    summary="Descarga el catálogo como planilla TSV",
    response_class=Response,
)
def exportar(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """Mismas columnas que la planilla de carga, así el archivo se puede
    editar y volver a importar. Lleva BOM para que Excel respete las tildes."""
    salida = io.StringIO()
    escritor = csv.DictWriter(
        salida, fieldnames=COLUMNAS_TSV, delimiter="\t", lineterminator="\n"
    )
    escritor.writeheader()
    for p in crud.listar_productos_admin(sesion):
        escritor.writerow(
            {
                "codigo": p.codigo,
                "nombre": p.nombre,
                "slug": p.slug,
                "marca_slug": p.marca.slug,
                "categoria_slug": p.subcategoria.categoria.slug,
                "subcategoria_slug": p.subcategoria.slug,
                "precio": f"{p.precio:.2f}",
                "precio_antes": f"{p.precio_antes:.2f}" if p.precio_antes else "",
                "presentacion": p.presentacion or "",
                "descripcion_corta": p.descripcion_corta or "",
                "descripcion_larga": p.descripcion_larga or "",
                "modo_uso": p.modo_uso or "",
                "beneficios": "|".join(p.beneficios or []),
                "stock": p.stock,
                "activo": str(p.activo).lower(),
                "destacado": str(p.destacado).lower(),
                "mas_vendido": str(p.mas_vendido).lower(),
            }
        )

    return Response(
        content="﻿" + salida.getvalue(),
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="catalogo.tsv"'},
    )


@router.post(
    "/importar",
    summary="Carga productos desde una planilla TSV",
    responses={422: {"description": "La planilla entera no sirve"}},
)
async def importar(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    archivo: Annotated[UploadFile, File(description="Planilla TSV")],
    simular: Annotated[
        bool, Query(description="Solo valida y cuenta; no guarda nada.")
    ] = False,
):
    """Crea los productos nuevos y actualiza los que ya existen, por `codigo`.

    Responde siempre con el mismo resumen: cuántos crea y actualiza, y la lista
    completa de errores por línea. Si hay algún error no se guarda nada: entra
    toda la planilla o ninguna. Con `simular` se comprueba sin guardar, para
    mostrar la vista previa antes de confirmar."""
    try:
        filas, avisos = importar_tsv.leer_planilla(await archivo.read())
    except importar_tsv.ErrorPlanilla as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    resultado = importar_tsv.procesar(sesion, filas, aplicar=not simular)
    return {**resultado, "avisos": avisos}


@router.get("/{codigo}", response_model=ProductoAdminOut, summary="Un producto")
def obtener(
    codigo: str,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    return _buscar(sesion, codigo)


@router.post(
    "",
    response_model=ProductoAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un producto",
)
def crear(
    datos: ProductoCrear,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    _validar_relaciones(sesion, datos.marca_id, datos.subcategoria_id)
    try:
        producto = crud.guardar_producto(sesion, datos.model_dump())
    except crud.ErrorCatalogo as error:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    sesion.commit()
    return crud.obtener_producto_admin(sesion, producto.codigo)


@router.put("/{codigo}", response_model=ProductoAdminOut, summary="Edita un producto")
def editar(
    codigo: str,
    datos: ProductoEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    producto = _buscar(sesion, codigo)
    _validar_relaciones(sesion, datos.marca_id, datos.subcategoria_id)
    try:
        crud.guardar_producto(sesion, datos.model_dump(), producto=producto)
    except crud.ErrorCatalogo as error:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    sesion.commit()
    return crud.obtener_producto_admin(sesion, codigo)


@router.patch(
    "/{codigo}/stock", response_model=ProductoAdminOut, summary="Cambia solo el stock"
)
def cambiar_stock(
    codigo: str,
    cambio: CambioStock,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    producto = _buscar(sesion, codigo)
    producto.stock = cambio.stock
    sesion.commit()
    return crud.obtener_producto_admin(sesion, codigo)


@router.patch(
    "/{codigo}/activo",
    response_model=ProductoAdminOut,
    summary="Activa o desactiva un producto",
)
def cambiar_activo(
    codigo: str,
    cambio: CambioActivo,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """No hay borrado: un producto desactivado desaparece de la tienda pero
    conserva su historial de pedidos."""
    producto = _buscar(sesion, codigo)
    producto.activo = cambio.activo
    sesion.commit()
    return crud.obtener_producto_admin(sesion, codigo)


# ── Fotos ────────────────────────────────────────────────────────────


@router.post(
    "/{codigo}/imagenes",
    response_model=ProductoAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Sube una foto a Cloudinary",
    responses={422: {"description": "Formato, tamaño o credenciales"}},
)
async def subir_imagen(
    codigo: str,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    archivo: Annotated[UploadFile, File()],
    tipo: Annotated[str | None, Form()] = None,
):
    producto = _buscar(sesion, codigo)
    siguiente = max((i.orden for i in producto.imagenes), default=0) + 1

    try:
        subida = fotos.subir(
            await archivo.read(),
            codigo=codigo,
            orden=siguiente,
            tipo_mime=archivo.content_type or "",
        )
    except fotos.ErrorFoto as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    sesion.add(
        ImagenProducto(
            id_producto=codigo,
            url=subida["url"],
            public_id=subida["public_id"],
            orden=siguiente,
            tipo=tipo,
        )
    )
    sesion.commit()
    return crud.obtener_producto_admin(sesion, codigo)


@router.delete(
    "/{codigo}/imagenes/{imagen_id}",
    response_model=ProductoAdminOut,
    summary="Borra una foto, también de Cloudinary",
)
def borrar_imagen(
    codigo: str,
    imagen_id: int,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    producto = _buscar(sesion, codigo)
    imagen = next((i for i in producto.imagenes if i.id == imagen_id), None)
    if imagen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El producto '{codigo}' no tiene una foto {imagen_id}.",
        )

    public_id = imagen.public_id or fotos.public_id_desde_url(imagen.url)
    if public_id:
        try:
            fotos.borrar(public_id)
        except fotos.ErrorFoto as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error

    sesion.delete(imagen)
    sesion.flush()
    # Sin esto, `producto.imagenes` seguiría trayendo la que acabamos de borrar.
    sesion.expire(producto, ["imagenes"])
    _renumerar(sesion, producto)
    sesion.commit()
    return crud.obtener_producto_admin(sesion, codigo)


@router.patch(
    "/{codigo}/imagenes/orden",
    response_model=ProductoAdminOut,
    summary="Reordena las fotos (la primera es la principal)",
)
def reordenar_imagenes(
    codigo: str,
    orden: OrdenImagenes,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    producto = _buscar(sesion, codigo)
    por_id = {i.id: i for i in producto.imagenes}
    if set(orden.ids) != set(por_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La lista debe traer exactamente las fotos del producto.",
        )

    # Se pasan a negativo primero porque (producto, orden) es único: sin eso,
    # dos fotos chocarían a mitad del reordenamiento.
    for imagen in producto.imagenes:
        imagen.orden = -imagen.orden
    sesion.flush()
    for posicion, imagen_id in enumerate(orden.ids, start=1):
        por_id[imagen_id].orden = posicion
    sesion.commit()
    return crud.obtener_producto_admin(sesion, codigo)


def _renumerar(sesion: Session, producto: Producto) -> None:
    """Deja los órdenes en 1, 2, 3… tras borrar una foto del medio.

    Pasan por negativo primero porque (producto, orden) es único: si no, al
    subir la segunda foto a la posición 1 chocaría con la que aún está ahí.
    """
    restantes = sorted(producto.imagenes, key=lambda i: i.orden)
    for imagen in restantes:
        imagen.orden = -imagen.orden
    sesion.flush()
    for posicion, imagen in enumerate(restantes, start=1):
        imagen.orden = posicion
    sesion.flush()
