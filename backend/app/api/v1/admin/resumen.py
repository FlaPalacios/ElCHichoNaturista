"""Resumen del negocio y clientes, ambos calculados desde los pedidos."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tienda as ajustes_tienda
from app.database import obtener_sesion
from app.models import Admin, EstadoPedido, Pedido, PedidoItem, Producto
from app.seguridad import admin_actual

router = APIRouter(tags=["admin"])

# Un pedido cuenta como venta desde que el pago está confirmado.
ESTADOS_VENDIDOS = (
    EstadoPedido.pago_confirmado,
    EstadoPedido.preparando,
    EstadoPedido.enviado,
    EstadoPedido.entregado,
)
ESTADOS_PENDIENTES = (EstadoPedido.nuevo, EstadoPedido.pago_confirmado)


class ProductoEscaso(BaseModel):
    codigo: str
    nombre: str
    stock: int


class MasVendido(BaseModel):
    codigo: str
    nombre: str
    unidades: int
    importe: Decimal


class PedidoBreve(BaseModel):
    numero_pedido: str
    nombre_contacto: str
    telefono_contacto: str
    estado: EstadoPedido
    total: Decimal
    creado_en: datetime


class Resumen(BaseModel):
    por_atender: int
    pedidos_del_mes: int
    ventas_del_mes: Decimal
    ticket_promedio: Decimal
    stock_bajo_desde: int
    productos_escasos: list[ProductoEscaso]
    top_del_mes: list[MasVendido]
    ultimos_pedidos: list[PedidoBreve]


class Cliente(BaseModel):
    """No hay tabla de clientes: cada teléfono que compró es un cliente."""

    telefono: str
    nombre: str
    correo: str | None = None
    pedidos: int
    total_gastado: Decimal
    ultima_compra: datetime
    ultimo_destino: str | None = None


def _inicio_del_mes() -> datetime:
    hoy = date.today()
    return datetime(hoy.year, hoy.month, 1, tzinfo=timezone.utc)


@router.get("/resumen", response_model=Resumen, summary="Cómo va el negocio")
def resumen(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    desde = _inicio_del_mes()
    umbral = ajustes_tienda.entero(sesion, "stock_bajo")

    por_atender = sesion.scalar(
        select(func.count(Pedido.id)).where(Pedido.estado.in_(ESTADOS_PENDIENTES))
    )

    del_mes = sesion.execute(
        select(func.count(Pedido.id), func.coalesce(func.sum(Pedido.total), 0)).where(
            Pedido.estado.in_(ESTADOS_VENDIDOS), Pedido.creado_en >= desde
        )
    ).one()
    cantidad, ventas = del_mes[0], Decimal(del_mes[1])

    escasos = sesion.scalars(
        select(Producto)
        .where(Producto.activo.is_(True), Producto.stock <= umbral)
        .order_by(Producto.stock, Producto.nombre)
        .limit(12)
    ).all()

    top = sesion.execute(
        select(
            Producto.codigo,
            Producto.nombre,
            func.sum(PedidoItem.cantidad).label("unidades"),
            func.sum(PedidoItem.cantidad * PedidoItem.precio_unitario).label("importe"),
        )
        .join(PedidoItem, PedidoItem.producto_id == Producto.id)
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .where(Pedido.estado.in_(ESTADOS_VENDIDOS), Pedido.creado_en >= desde)
        .group_by(Producto.codigo, Producto.nombre)
        .order_by(func.sum(PedidoItem.cantidad).desc())
        .limit(5)
    ).all()

    ultimos = sesion.scalars(
        select(Pedido).order_by(Pedido.creado_en.desc()).limit(8)
    ).all()

    return Resumen(
        por_atender=por_atender,
        pedidos_del_mes=cantidad,
        ventas_del_mes=ventas,
        ticket_promedio=(ventas / cantidad) if cantidad else Decimal("0"),
        stock_bajo_desde=umbral,
        productos_escasos=[
            ProductoEscaso(codigo=p.codigo, nombre=p.nombre, stock=p.stock) for p in escasos
        ],
        top_del_mes=[
            MasVendido(codigo=c, nombre=n, unidades=u, importe=i) for c, n, u, i in top
        ],
        ultimos_pedidos=[PedidoBreve.model_validate(p, from_attributes=True) for p in ultimos],
    )


@router.get("/clientes", response_model=list[Cliente], summary="Clientes, según sus pedidos")
def clientes(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    """Se agrupan por teléfono, que es lo único que siempre está: se compra
    como invitado, sin registro."""
    filas = sesion.execute(
        select(
            Pedido.telefono_contacto,
            func.max(Pedido.nombre_contacto).label("nombre"),
            func.max(Pedido.email_contacto).label("correo"),
            func.count(Pedido.id).label("pedidos"),
            func.sum(Pedido.total).label("gastado"),
            func.max(Pedido.creado_en).label("ultima"),
        )
        .where(Pedido.estado != EstadoPedido.no_concretado)
        .group_by(Pedido.telefono_contacto)
        .order_by(func.max(Pedido.creado_en).desc())
    ).all()

    # El destino del último pedido, para saber a dónde se le suele despachar.
    destinos = {
        telefono: f"{distrito}, {departamento}"
        for telefono, distrito, departamento in sesion.execute(
            select(Pedido.telefono_contacto, Pedido.distrito, Pedido.departamento)
            .order_by(Pedido.creado_en)
        ).all()
    }

    return [
        Cliente(
            telefono=f.telefono_contacto,
            nombre=f.nombre,
            correo=f.correo,
            pedidos=f.pedidos,
            total_gastado=f.gastado,
            ultima_compra=f.ultima,
            ultimo_destino=destinos.get(f.telefono_contacto),
        )
        for f in filas
    ]
