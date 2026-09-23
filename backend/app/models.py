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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EstadoPedido(str, enum.Enum):
    """Estados por los que pasa un pedido coordinado por WhatsApp.

    El camino normal es nuevo → pago_confirmado → preparando → enviado →
    entregado. `cancelado` y `no_concretado` son finales: el primero cuando se
    cancela un pedido que iba en serio, el segundo cuando el cliente nunca
    llegó a confirmar.
    """

    nuevo = "nuevo"
    pago_confirmado = "pago_confirmado"
    preparando = "preparando"
    enviado = "enviado"
    entregado = "entregado"
    cancelado = "cancelado"
    no_concretado = "no_concretado"


class Marca(Base):
    """Green House / HIRI, Henna Colors, Fit Rex, Algarrobos Orgánicos."""

    __tablename__ = "marcas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    productos: Mapped[list["Producto"]] = relationship(back_populates="marca")

    def __repr__(self) -> str:
        return f"<Marca {self.slug}>"


class Categoria(Base):
    """Nivel de arriba del catálogo: Frescos, Abarrotes, Cuidado Personal."""

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    subcategorias: Mapped[list["Subcategoria"]] = relationship(
        back_populates="categoria", order_by="Subcategoria.orden"
    )

    def __repr__(self) -> str:
        return f"<Categoria {self.slug}>"


class Subcategoria(Base):
    """Nivel de abajo: cuelga de una categoría y es lo que clasifica al producto."""

    __tablename__ = "subcategorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    categoria: Mapped[Categoria] = relationship(back_populates="subcategorias", lazy="joined")
    productos: Mapped[list["Producto"]] = relationship(back_populates="subcategoria")

    __table_args__ = (Index("ix_subcategorias_categoria_id", "categoria_id"),)

    def __repr__(self) -> str:
        return f"<Subcategoria {self.slug}>"


class ImagenProducto(Base):
    """Fotos alojadas en Cloudinary. La de `orden` 1 es la principal."""

    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Apunta a productos.codigo, no a productos.id: los códigos del negocio
    # sobreviven a una recarga del catálogo.
    id_producto: Mapped[str] = mapped_column(
        ForeignKey("productos.codigo", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Identificador en Cloudinary, para poder borrarla. Las fotos cargadas por
    # planilla no lo traen y se deduce de la URL.
    public_id: Mapped[str | None] = mapped_column(String(255))
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(50))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    producto: Mapped["Producto"] = relationship(back_populates="imagenes")

    __table_args__ = (
        UniqueConstraint("id_producto", "orden", name="uq_product_images_producto_orden"),
        Index("ix_product_images_id_producto", "id_producto"),
    )

    def __repr__(self) -> str:
        return f"<ImagenProducto {self.id_producto} #{self.orden}>"


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Identificador del negocio (ECN-001): es la clave con la que Fernando
    # trabaja su catálogo y la que relaciona las imágenes.
    codigo: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    descripcion_corta: Mapped[str | None] = mapped_column(Text)
    marca_id: Mapped[int] = mapped_column(
        ForeignKey("marcas.id", ondelete="RESTRICT"), nullable=False
    )
    # La categoría del producto es la de su subcategoría: no se guarda aparte
    # para que no puedan contradecirse.
    subcategoria_id: Mapped[int] = mapped_column(
        ForeignKey("subcategorias.id", ondelete="RESTRICT"), nullable=False
    )
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Precio anterior tachado en la ficha. Null = no está en oferta.
    precio_antes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    destacado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    mas_vendido: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Contenido de la ficha de producto (migración 0002)
    presentacion: Mapped[str | None] = mapped_column(String(120))
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

    marca: Mapped[Marca] = relationship(back_populates="productos", lazy="joined")
    subcategoria: Mapped[Subcategoria] = relationship(
        back_populates="productos", lazy="joined"
    )
    items: Mapped[list["PedidoItem"]] = relationship(back_populates="producto")
    imagenes: Mapped[list[ImagenProducto]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by=ImagenProducto.orden,
        lazy="selectin",
    )

    @property
    def categoria(self) -> Categoria:
        """Atajo: la categoría del producto es la de su subcategoría."""
        return self.subcategoria.categoria

    __table_args__ = (
        Index("ix_productos_marca_id", "marca_id"),
        Index("ix_productos_subcategoria_id", "subcategoria_id"),
        Index("ix_productos_activo", "activo"),
    )

    def __repr__(self) -> str:
        return f"<Producto {self.slug}>"


class Departamento(Base):
    """Ubigeo del INEI: departamento → provincia → distrito."""

    __tablename__ = "departamentos"

    codigo: Mapped[str] = mapped_column(String(2), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)

    provincias: Mapped[list["Provincia"]] = relationship(
        back_populates="departamento", order_by="Provincia.nombre"
    )

    def __repr__(self) -> str:
        return f"<Departamento {self.nombre}>"


class Provincia(Base):
    __tablename__ = "provincias"

    codigo: Mapped[str] = mapped_column(String(4), primary_key=True)
    departamento_codigo: Mapped[str] = mapped_column(
        ForeignKey("departamentos.codigo", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)

    departamento: Mapped[Departamento] = relationship(back_populates="provincias")
    distritos: Mapped[list["Distrito"]] = relationship(
        back_populates="provincia", order_by="Distrito.nombre"
    )

    __table_args__ = (Index("ix_provincias_departamento", "departamento_codigo"),)

    def __repr__(self) -> str:
        return f"<Provincia {self.nombre}>"


class Distrito(Base):
    __tablename__ = "distritos"

    codigo: Mapped[str] = mapped_column(String(6), primary_key=True)
    provincia_codigo: Mapped[str] = mapped_column(
        ForeignKey("provincias.codigo", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)

    provincia: Mapped[Provincia] = relationship(back_populates="distritos", lazy="joined")

    __table_args__ = (Index("ix_distritos_provincia", "provincia_codigo"),)

    def __repr__(self) -> str:
        return f"<Distrito {self.nombre}>"


class TarifaEnvio(Base):
    """Cuánto cuesta enviar a una zona.

    Una fila por departamento es la tarifa base; una fila con `provincia_codigo`
    afina esa provincia en concreto. Así Lima capital cobra distinto que el
    resto del departamento de Lima sin duplicar 128 filas.
    """

    __tablename__ = "tarifas_envio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    departamento_codigo: Mapped[str] = mapped_column(
        ForeignKey("departamentos.codigo", ondelete="CASCADE"), nullable=False
    )
    provincia_codigo: Mapped[str | None] = mapped_column(
        ForeignKey("provincias.codigo", ondelete="CASCADE")
    )
    costo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    departamento: Mapped[Departamento] = relationship(lazy="joined")
    provincia: Mapped[Provincia | None] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "departamento_codigo", "provincia_codigo", name="uq_tarifas_envio_zona"
        ),
    )

    def __repr__(self) -> str:
        return f"<TarifaEnvio {self.provincia_codigo or self.departamento_codigo}>"


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
    email_contacto: Mapped[str | None] = mapped_column(String(150))

    # A dónde va. Los nombres se guardan copiados (no por FK) para que el
    # pedido conserve su dirección aunque cambie la tabla de ubigeo.
    direccion_envio: Mapped[str] = mapped_column(Text, nullable=False)
    departamento: Mapped[str | None] = mapped_column(String(100))
    provincia: Mapped[str | None] = mapped_column(String(100))
    distrito: Mapped[str | None] = mapped_column(String(100))
    ubigeo: Mapped[str | None] = mapped_column(String(6))
    referencia: Mapped[str | None] = mapped_column(Text)

    estado: Mapped[EstadoPedido] = mapped_column(
        Enum(EstadoPedido, name="estado_pedido", native_enum=True, validate_strings=True),
        nullable=False,
        server_default=EstadoPedido.nuevo.value,
    )
    envio: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    nota: Mapped[str | None] = mapped_column(Text)

    # Solo para el panel: el cliente nunca ve esto.
    courier: Mapped[str | None] = mapped_column(String(100))
    codigo_seguimiento: Mapped[str | None] = mapped_column(String(100))
    nota_interna: Mapped[str | None] = mapped_column(Text)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    cliente: Mapped[Cliente | None] = relationship(back_populates="pedidos")
    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )

    @property
    def subtotal(self) -> Decimal:
        """Suma de los items. Nunca se guarda: se calcula siempre desde ellos."""
        return sum(
            (item.cantidad * item.precio_unitario for item in self.items), Decimal("0.00")
        )

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


class Configuracion(Base):
    """Ajustes de la tienda editables desde el panel (clave-valor).

    Los valores por defecto y el tipo de cada clave están en `app/tienda.py`:
    acá solo se guarda lo que se cambió.
    """

    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Configuracion {self.clave}>"


class Admin(Base):
    """Usuario único de administración (etapa 6)."""

    __tablename__ = "admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<Admin {self.usuario}>"
