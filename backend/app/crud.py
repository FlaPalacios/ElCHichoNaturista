"""Consultas a la base de datos. Las rutas no arman SQL: llaman a esto."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Categoria, Producto


def listar_categorias(sesion: Session) -> list[Categoria]:
    consulta = select(Categoria).order_by(Categoria.orden, Categoria.nombre)
    return list(sesion.scalars(consulta))


def obtener_categoria_por_slug(sesion: Session, slug: str) -> Categoria | None:
    return sesion.scalar(select(Categoria).where(Categoria.slug == slug))


def _escapar_like(termino: str) -> str:
    """Neutraliza los comodines de LIKE para que el usuario busque texto literal."""
    return termino.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def listar_productos(
    sesion: Session,
    *,
    categoria: str | None = None,
    precio_min: Decimal | None = None,
    precio_max: Decimal | None = None,
    q: str | None = None,
    destacado: bool | None = None,
    mas_vendido: bool | None = None,
    en_oferta: bool | None = None,
    solo_activos: bool = True,
) -> list[Producto]:
    consulta = select(Producto)

    if solo_activos:
        consulta = consulta.where(Producto.activo.is_(True))

    if categoria:
        consulta = consulta.join(Producto.categoria).where(Categoria.slug == categoria)

    if precio_min is not None:
        consulta = consulta.where(Producto.precio >= precio_min)

    if precio_max is not None:
        consulta = consulta.where(Producto.precio <= precio_max)

    if q:
        patron = f"%{_escapar_like(q.strip())}%"
        consulta = consulta.where(
            Producto.nombre.ilike(patron, escape="\\")
            | Producto.descripcion_corta.ilike(patron, escape="\\")
        )

    if destacado is not None:
        consulta = consulta.where(Producto.destacado.is_(destacado))

    if mas_vendido is not None:
        consulta = consulta.where(Producto.mas_vendido.is_(mas_vendido))

    if en_oferta is not None:
        if en_oferta:
            consulta = consulta.where(Producto.precio_antes.is_not(None))
        else:
            consulta = consulta.where(Producto.precio_antes.is_(None))

    # Los destacados primero; dentro de cada grupo, por nombre.
    consulta = consulta.order_by(Producto.destacado.desc(), Producto.nombre)

    return list(sesion.scalars(consulta).unique())


def obtener_producto_por_slug(
    sesion: Session, slug: str, *, solo_activos: bool = True
) -> Producto | None:
    consulta = select(Producto).where(Producto.slug == slug)
    if solo_activos:
        consulta = consulta.where(Producto.activo.is_(True))
    return sesion.scalars(consulta).unique().one_or_none()
