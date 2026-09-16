"""Esquemas Pydantic: la forma en que la API entrega los datos."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import EstadoPedido, MetodoPago


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    slug: str
    orden: int


class CategoriaBreve(BaseModel):
    """Categoría anidada dentro de un producto."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    slug: str


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    slug: str
    descripcion_corta: str | None = None
    descripcion_larga: str | None = None
    modo_uso: str | None = None
    presentacion: str | None = None
    origen: str | None = None
    beneficios: list[str] = []
    precio: Decimal = Field(examples=["34.90"])
    precio_antes: Decimal | None = Field(default=None, examples=["42.00"])
    imagen_url: str | None = None
    stock: int
    activo: bool
    destacado: bool
    mas_vendido: bool
    categoria: CategoriaBreve
    creado_en: datetime
    actualizado_en: datetime | None = None


class Salud(BaseModel):
    estado: str
    base_de_datos: str
    version: str


# ── Pedidos ──────────────────────────────────────────────────────────


class PedidoItemEntrada(BaseModel):
    """Lo que manda el cliente por cada línea: sin precio, eso lo pone la API."""

    producto_id: int
    cantidad: int = Field(gt=0, le=99, examples=[2])


class PedidoCrear(BaseModel):
    """Payload de `POST /pedidos`. `correo` no se valida como email estricto:
    es opcional y hoy tampoco se exige en el frontend."""

    nombre_contacto: str = Field(min_length=3, max_length=150, examples=["Ana Torres"])
    telefono_contacto: str = Field(min_length=9, max_length=20, examples=["987654321"])
    correo: str | None = Field(default=None, max_length=150)
    entrega: Literal["delivery", "tienda"]
    direccion: str | None = Field(default=None, max_length=300)
    distrito: str | None = Field(default=None, max_length=100)
    referencia: str | None = Field(default=None, max_length=300)
    metodo_pago: MetodoPago
    nota: str | None = Field(default=None, max_length=1000)
    items: list[PedidoItemEntrada] = Field(min_length=1)


class ProductoBreve(BaseModel):
    """Producto anidado dentro de un item de pedido, igual que CategoriaBreve."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    slug: str


class PedidoItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    producto: ProductoBreve
    cantidad: int
    precio_unitario: Decimal = Field(examples=["34.90"])


class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numero_pedido: str = Field(examples=["ECN-260915-4471"])
    estado: EstadoPedido
    nombre_contacto: str
    telefono_contacto: str
    email_contacto: str | None = None
    entrega: Literal["delivery", "tienda"]
    direccion_envio: str | None = None
    distrito: str | None = None
    referencia: str | None = None
    metodo_pago: MetodoPago | None = None
    nota: str | None = None
    subtotal: Decimal = Field(examples=["69.80"])
    envio: Decimal = Field(examples=["12.00"])
    total: Decimal = Field(examples=["81.80"])
    items: list[PedidoItemOut]
    creado_en: datetime
