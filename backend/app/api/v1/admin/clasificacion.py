"""Categorías, subcategorías y marcas desde el panel.

Las marcas viven acá y no en su propia sección porque son lo mismo desde el
punto de vista de quien carga el catálogo: las tres listas con las que se
clasifica un producto.
"""

import re
import unicodedata
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.models import Admin, Categoria, Marca, Producto, Subcategoria
from app.schemas import Breve
from app.seguridad import admin_actual

router = APIRouter(tags=["admin"])


def slugificar(texto: str) -> str:
    """'Café y cacao' → 'cafe-y-cacao'."""
    sin_tildes = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")


class CategoriaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    # Si no se manda, sale del nombre.
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")
    orden: int = 0
    activo: bool = True


class SubcategoriaEntrada(CategoriaEntrada):
    categoria_id: int


class MarcaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")
    orden: int = 0


class SubcategoriaAdminOut(Breve):
    categoria_id: int
    orden: int
    activo: bool
    productos: int


class CategoriaAdminOut(Breve):
    orden: int
    activo: bool
    productos: int
    subcategorias: list[SubcategoriaAdminOut]


class MarcaAdminOut(Breve):
    orden: int
    productos: int


def _slug_libre(sesion: Session, modelo, slug: str, excepto: int | None = None) -> str:
    choque = sesion.scalar(select(modelo).where(modelo.slug == slug))
    if choque is not None and choque.id != excepto:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ya existe algo con la dirección '{slug}'. Usa otro nombre.",
        )
    return slug


def _cuantos_productos(sesion: Session, columna) -> dict[int, int]:
    filas = sesion.execute(
        select(columna, func.count(Producto.id)).group_by(columna)
    ).all()
    return {clave: total for clave, total in filas}


@router.get(
    "/clasificacion",
    summary="Categorías con sus subcategorías, y las marcas",
)
def listar_clasificacion(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """Todo, activo o no: el panel necesita ver también lo que la tienda oculta."""
    por_subcategoria = _cuantos_productos(sesion, Producto.subcategoria_id)
    por_marca = _cuantos_productos(sesion, Producto.marca_id)

    categorias = []
    for c in sesion.scalars(select(Categoria).order_by(Categoria.orden, Categoria.nombre)):
        subs = sorted(c.subcategorias, key=lambda s: (s.orden, s.nombre))
        categorias.append(
            CategoriaAdminOut(
                id=c.id,
                nombre=c.nombre,
                slug=c.slug,
                orden=c.orden,
                activo=c.activo,
                productos=sum(por_subcategoria.get(s.id, 0) for s in subs),
                subcategorias=[
                    SubcategoriaAdminOut(
                        id=s.id,
                        nombre=s.nombre,
                        slug=s.slug,
                        categoria_id=s.categoria_id,
                        orden=s.orden,
                        activo=s.activo,
                        productos=por_subcategoria.get(s.id, 0),
                    )
                    for s in subs
                ],
            )
        )

    marcas = [
        MarcaAdminOut(
            id=m.id,
            nombre=m.nombre,
            slug=m.slug,
            orden=m.orden,
            productos=por_marca.get(m.id, 0),
        )
        for m in sesion.scalars(select(Marca).order_by(Marca.orden, Marca.nombre))
    ]
    return {"categorias": categorias, "marcas": marcas}


# ── Categorías ───────────────────────────────────────────────────────


@router.post(
    "/categorias",
    response_model=Breve,
    status_code=status.HTTP_201_CREATED,
    summary="Crea una categoría",
)
def crear_categoria(
    datos: CategoriaEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    slug = _slug_libre(sesion, Categoria, datos.slug or slugificar(datos.nombre))
    categoria = Categoria(
        nombre=datos.nombre, slug=slug, orden=datos.orden, activo=datos.activo
    )
    sesion.add(categoria)
    sesion.commit()
    return categoria


@router.put("/categorias/{categoria_id}", response_model=Breve, summary="Edita una categoría")
def editar_categoria(
    categoria_id: int,
    datos: CategoriaEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    categoria = sesion.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa categoría.")
    categoria.slug = _slug_libre(
        sesion, Categoria, datos.slug or slugificar(datos.nombre), categoria_id
    )
    categoria.nombre = datos.nombre
    categoria.orden = datos.orden
    categoria.activo = datos.activo
    sesion.commit()
    return categoria


@router.delete(
    "/categorias/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borra una categoría vacía",
)
def borrar_categoria(
    categoria_id: int,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """Solo si no cuelga nada de ella: así no se pierde el rastro de un producto."""
    categoria = sesion.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa categoría.")
    if categoria.subcategorias:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esa categoría todavía tiene subcategorías. Bórralas o muévelas primero.",
        )
    sesion.delete(categoria)
    sesion.commit()


# ── Subcategorías ────────────────────────────────────────────────────


@router.post(
    "/subcategorias",
    response_model=Breve,
    status_code=status.HTTP_201_CREATED,
    summary="Crea una subcategoría",
)
def crear_subcategoria(
    datos: SubcategoriaEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    if sesion.get(Categoria, datos.categoria_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No existe esa categoría."
        )
    slug = _slug_libre(sesion, Subcategoria, datos.slug or slugificar(datos.nombre))
    sub = Subcategoria(
        nombre=datos.nombre,
        slug=slug,
        categoria_id=datos.categoria_id,
        orden=datos.orden,
        activo=datos.activo,
    )
    sesion.add(sub)
    sesion.commit()
    return sub


@router.put(
    "/subcategorias/{subcategoria_id}",
    response_model=Breve,
    summary="Edita una subcategoría",
)
def editar_subcategoria(
    subcategoria_id: int,
    datos: SubcategoriaEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    sub = sesion.get(Subcategoria, subcategoria_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa subcategoría.")
    if sesion.get(Categoria, datos.categoria_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No existe esa categoría."
        )
    sub.slug = _slug_libre(
        sesion, Subcategoria, datos.slug or slugificar(datos.nombre), subcategoria_id
    )
    sub.nombre = datos.nombre
    sub.categoria_id = datos.categoria_id
    sub.orden = datos.orden
    sub.activo = datos.activo
    sesion.commit()
    return sub


@router.delete(
    "/subcategorias/{subcategoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borra una subcategoría sin productos",
)
def borrar_subcategoria(
    subcategoria_id: int,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    sub = sesion.get(Subcategoria, subcategoria_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa subcategoría.")
    cuantos = sesion.scalar(
        select(func.count(Producto.id)).where(Producto.subcategoria_id == subcategoria_id)
    )
    if cuantos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tiene {cuantos} producto(s). Muévelos a otra subcategoría primero.",
        )
    sesion.delete(sub)
    sesion.commit()


# ── Marcas ───────────────────────────────────────────────────────────


@router.post(
    "/marcas",
    response_model=Breve,
    status_code=status.HTTP_201_CREATED,
    summary="Crea una marca",
)
def crear_marca(
    datos: MarcaEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    slug = _slug_libre(sesion, Marca, datos.slug or slugificar(datos.nombre))
    marca = Marca(nombre=datos.nombre, slug=slug, orden=datos.orden)
    sesion.add(marca)
    sesion.commit()
    return marca


@router.put("/marcas/{marca_id}", response_model=Breve, summary="Edita una marca")
def editar_marca(
    marca_id: int,
    datos: MarcaEntrada,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    marca = sesion.get(Marca, marca_id)
    if marca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa marca.")
    marca.slug = _slug_libre(
        sesion, Marca, datos.slug or slugificar(datos.nombre), marca_id
    )
    marca.nombre = datos.nombre
    marca.orden = datos.orden
    sesion.commit()
    return marca


@router.delete(
    "/marcas/{marca_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borra una marca sin productos",
)
def borrar_marca(
    marca_id: int,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    marca = sesion.get(Marca, marca_id)
    if marca is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa marca.")
    cuantos = sesion.scalar(
        select(func.count(Producto.id)).where(Producto.marca_id == marca_id)
    )
    if cuantos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tiene {cuantos} producto(s). Cámbiales la marca primero.",
        )
    sesion.delete(marca)
    sesion.commit()
