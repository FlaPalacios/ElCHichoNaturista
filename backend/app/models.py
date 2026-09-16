"""Modelos de SQLAlchemy.

El esquema completo se crea de una vez (ver la migración 0001), aunque los
endpoints se construyan por etapas: pedidos, clientes y admin ya tienen sus
tablas listas para las etapas 5 y 6.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EstadoPedido(str, enum.Enum):
    """Estados por los que pasa un pedido coordinado por WhatsApp."""

    pendiente = "pendiente"
    coordinado = "coordinado"
    enviado = "enviado"
    completado = "completado"
    cancelado = "cancelado"


class MetodoPago(str, enum.Enum):
    """Cómo piensa pagar el cliente, coordinado luego por el chat."""

    yape = "yape"
    transferencia = "transferencia"
    contraentrega = "contraentrega"


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    productos: Mapped[list["Producto"]] = relationship(back_populates="categoria")

    def __repr__(self) -> str:
        return f"<Categoria {self.slug}>"


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    descripcion_corta: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False
    )
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Precio anterior tachado en la ficha. Null = no está en oferta.
    precio_antes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    imagen_url: Mapped[str | None] = mapped_column(Text)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    destacado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    mas_vendido: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Contenido de la ficha de producto (migración 0002)
    presentacion: Mapped[str | None] = mapped_column(String(120))
    origen: Mapped[str | None] = mapped_column(String(150))
    descripcion_larga: Mapped[str | None] = mapped_column(Text)
    modo_uso: Mapped[str | None] = mapped_column(Text)
    beneficios: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    categoria: Mapped[Categoria] = relationship(back_populates="productos", lazy="joined")
    items: Mapped[list["PedidoItem"]] = relationship(back_populates="producto")

    __table_args__ = (
        Index("ix_productos_categoria_id", "categoria_id"),
        Index("ix_productos_activo", "activo"),
    )

    def __repr__(self) -> str:
        return f"<Producto {self.slug}>"


class Cliente(Base):
    """Opcional: se puede comprar como invitado, sin registro."""

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    telefono: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="cliente")

    def __repr__(self) -> str:
        return f"<Cliente {self.email}>"


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_pedido: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL")
    )
    nombre_contacto: Mapped[str] = mapped_column(String(150), nullable=False)
    telefono_contacto: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion_envio: Mapped[str | None] = mapped_column(Text)
    departamento: Mapped[str | None] = mapped_column(String(100))
    estado: Mapped[EstadoPedido] = mapped_column(
        Enum(EstadoPedido, name="estado_pedido", native_enum=True, validate_strings=True),
        nullable=False,
        server_default=EstadoPedido.pendiente.value,
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Datos del checkout (migración 0003). Nullable porque solo aplican a
    # entrega por delivery (distrito, referencia) o son opcionales (correo,
    # nota); metodo_pago se exige en la API, no acá.
    distrito: Mapped[str | None] = mapped_column(String(100))
    referencia: Mapped[str | None] = mapped_column(Text)
    email_contacto: Mapped[str | None] = mapped_column(String(150))
    nota: Mapped[str | None] = mapped_column(Text)
    metodo_pago: Mapped[MetodoPago | None] = mapped_column(
        Enum(MetodoPago, name="metodo_pago_pedido", native_enum=True, validate_strings=True)
    )

    cliente: Mapped[Cliente | None] = relationship(back_populates="pedidos")
    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )

    @property
    def entrega(self) -> str:
        """'tienda' si no hay dirección de envío, 'delivery' si la hay."""
        return "tienda" if self.direccion_envio is None else "delivery"

    @property
    def subtotal(self) -> Decimal:
        """Suma de los items. Nunca se guarda: se calcula siempre desde ellos."""
        return sum(
            (item.cantidad * item.precio_unitario for item in self.items), Decimal("0.00")
        )

    @property
    def envio(self) -> Decimal:
        """`total` es la única cifra persistida; el envío es la diferencia."""
        return self.total - self.subtotal

    def __repr__(self) -> str:
        return f"<Pedido {self.numero_pedido}>"


class PedidoItem(Base):
    __tablename__ = "pedido_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False
    )
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    # Copia del precio al momento de la compra: si el producto sube, el
    # pedido histórico no cambia.
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    pedido: Mapped[Pedido] = relationship(back_populates="items")
    producto: Mapped[Producto] = relationship(back_populates="items")

    __table_args__ = (
        Index("ix_pedido_items_pedido_id", "pedido_id"),
        Index("ix_pedido_items_producto_id", "producto_id"),
    )

    def __repr__(self) -> str:
        return f"<PedidoItem pedido={self.pedido_id} producto={self.producto_id}>"


class Admin(Base):
    """Usuario único de administración (etapa 6)."""

    __tablename__ = "admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<Admin {self.usuario}>"
