"""Consultas a la base de datos. Las rutas no arman SQL: llaman a esto."""

import random
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Categoria, MetodoPago, Pedido, PedidoItem, Producto


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


# ── Pedidos ──────────────────────────────────────────────────────────


class ErrorPedido(Exception):
    """Error de negocio al crear un pedido. La ruta lo traduce a HTTPException."""


class ProductoNoDisponible(ErrorPedido):
    def __init__(self, producto_id: int):
        super().__init__(f"El producto {producto_id} no existe o no está disponible.")
        self.producto_id = producto_id


class StockInsuficiente(ErrorPedido):
    def __init__(self, producto_id: int, nombre: str, disponible: int, solicitado: int):
        super().__init__(
            f"Stock insuficiente para '{nombre}': quedan {disponible}, se pidieron {solicitado}."
        )
        self.producto_id = producto_id
        self.disponible = disponible
        self.solicitado = solicitado


def _numero_candidato() -> str:
    hoy = date.today()
    azar = random.randint(1000, 9999)
    return f"ECN-{hoy:%y%m%d}-{azar}"


def generar_numero_pedido(sesion: Session, *, intentos: int = 20) -> str:
    """Formato ECN-AAMMDD-NNNN, igual al que ya generaba el frontend."""
    for _ in range(intentos):
        candidato = _numero_candidato()
        existe = sesion.scalar(select(Pedido.id).where(Pedido.numero_pedido == candidato))
        if existe is None:
            return candidato
    raise ErrorPedido("No se pudo generar un número de pedido único.")


def crear_pedido(
    sesion: Session,
    *,
    nombre_contacto: str,
    telefono_contacto: str,
    correo: str | None,
    entrega: str,  # "delivery" | "tienda"
    direccion: str | None,
    distrito: str | None,
    referencia: str | None,
    metodo_pago: MetodoPago,
    nota: str | None,
    items: Sequence[tuple[int, int]],  # (producto_id, cantidad)
    costo_envio_lima: Decimal,
    envio_gratis_desde: Decimal,
) -> Pedido:
    """Valida stock y arma el pedido con precios reales de la base.

    No hace commit: eso lo decide quien llama, igual que en seed.py.
    """
    ids = [producto_id for producto_id, _ in items]
    productos = {
        p.id: p for p in sesion.scalars(select(Producto).where(Producto.id.in_(ids)))
    }

    subtotal = Decimal("0.00")
    for producto_id, cantidad in items:
        producto = productos.get(producto_id)
        if producto is None or not producto.activo:
            raise ProductoNoDisponible(producto_id)
        if producto.stock < cantidad:
            raise StockInsuficiente(producto_id, producto.nombre, producto.stock, cantidad)
        subtotal += producto.precio * cantidad

    es_delivery = entrega == "delivery"
    envio = (
        costo_envio_lima
        if es_delivery and subtotal < envio_gratis_desde
        else Decimal("0.00")
    )

    pedido = Pedido(
        numero_pedido=generar_numero_pedido(sesion),
        nombre_contacto=nombre_contacto,
        telefono_contacto=telefono_contacto,
        email_contacto=correo,
        direccion_envio=direccion if es_delivery else None,
        distrito=distrito if es_delivery else None,
        referencia=referencia if es_delivery else None,
        metodo_pago=metodo_pago,
        nota=nota,
        total=subtotal + envio,
    )
    sesion.add(pedido)
    sesion.flush()  # asigna pedido.id

    for producto_id, cantidad in items:
        sesion.add(
            PedidoItem(
                pedido_id=pedido.id,
                producto_id=producto_id,
                cantidad=cantidad,
                precio_unitario=productos[producto_id].precio,
            )
        )
    sesion.flush()
    return pedido


def obtener_pedido_por_numero(sesion: Session, numero_pedido: str) -> Pedido | None:
    consulta = (
        select(Pedido)
        .options(selectinload(Pedido.items).joinedload(PedidoItem.producto))
        .where(Pedido.numero_pedido == numero_pedido)
    )
    return sesion.scalars(consulta).unique().one_or_none()
