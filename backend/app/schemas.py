"""Esquemas Pydantic: la forma en que la API entrega los datos."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import EstadoPedido


class Breve(BaseModel):
    """Lo mínimo para pintar un enlace: sirve a marca, categoría y subcategoría."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    slug: str


class SubcategoriaOut(Breve):
    orden: int


class CategoriaOut(Breve):
    orden: int
    subcategorias: list[SubcategoriaOut] = []


class SubcategoriaBreve(Breve):
    """Subcategoría anidada dentro de un producto, con su categoría."""

    categoria: Breve


class ImagenOut(BaseModel):
    """Foto de Cloudinary. La de `orden` 1 es la principal del producto."""

    model_config = ConfigDict(from_attributes=True)

    url: str
    orden: int
    tipo: str | None = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    slug: str
    descripcion_corta: str | None = None
    descripcion_larga: str | None = None
    modo_uso: str | None = None
    presentacion: str | None = None
    beneficios: list[str] = []
    precio: Decimal = Field(examples=["34.90"])
    precio_antes: Decimal | None = Field(default=None, examples=["42.00"])
    imagenes: list[ImagenOut] = []
    stock: int
    activo: bool
    destacado: bool
    mas_vendido: bool
    marca: Breve
    subcategoria: SubcategoriaBreve
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
    direccion: str = Field(min_length=5, max_length=300, examples=["Av. Siempre Viva 123"])
    # Código INEI del distrito de entrega: de ahí salen el departamento, la
    # provincia y el costo del envío.
    ubigeo: str = Field(min_length=6, max_length=6, examples=["150122"])
    referencia: str | None = Field(default=None, max_length=300)
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
    direccion_envio: str
    departamento: str | None = None
    provincia: str | None = None
    distrito: str | None = None
    ubigeo: str | None = None
    referencia: str | None = None
    nota: str | None = None
    subtotal: Decimal = Field(examples=["69.80"])
    envio: Decimal = Field(examples=["10.00"])
    total: Decimal = Field(examples=["81.80"])
    items: list[PedidoItemOut]
    creado_en: datetime


class PedidoAdminOut(PedidoOut):
    """Lo mismo que ve el cliente, más lo que solo existe en el panel."""

    courier: str | None = None
    codigo_seguimiento: str | None = None
    nota_interna: str | None = None


# ── Panel: catálogo ──────────────────────────────────────────────────


class ImagenAdminOut(ImagenOut):
    id: int


class ProductoAdminOut(ProductoOut):
    """Lo que ve el panel: incluye los inactivos y el id de cada foto."""

    imagenes: list[ImagenAdminOut] = []
    creado_en: datetime
    actualizado_en: datetime | None = None


class ProductoEntrada(BaseModel):
    """Campos que el panel manda al crear o editar un producto."""

    nombre: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=2, max_length=150, pattern=r"^[a-z0-9-]+$")
    marca_id: int
    subcategoria_id: int
    precio: Decimal = Field(ge=0, examples=["28.50"])
    precio_antes: Decimal | None = Field(default=None, ge=0)
    stock: int = Field(ge=0, le=99999)
    activo: bool = True
    destacado: bool = False
    mas_vendido: bool = False
    presentacion: str | None = Field(default=None, max_length=120)
    descripcion_corta: str | None = None
    descripcion_larga: str | None = None
    modo_uso: str | None = None
    beneficios: list[str] = []

    @model_validator(mode="after")
    def _oferta_coherente(self):
        """Un precio tachado que no sea mayor que el vigente no es una oferta."""
        if self.precio_antes is not None and self.precio_antes <= self.precio:
            raise ValueError("El precio anterior debe ser mayor que el precio actual.")
        return self


class ProductoCrear(ProductoEntrada):
    codigo: str = Field(min_length=3, max_length=10, pattern=r"^[A-Z0-9-]+$")


class CambioStock(BaseModel):
    stock: int = Field(ge=0, le=99999)


class CambioActivo(BaseModel):
    activo: bool


class ImagenEntrada(BaseModel):
    tipo: str | None = Field(default=None, max_length=50)


class OrdenImagenes(BaseModel):
    """Los ids de las fotos en el orden nuevo; la primera es la principal."""

    ids: list[int] = Field(min_length=1)


# ── Ubigeo ───────────────────────────────────────────────────────────


class LugarOut(BaseModel):
    """Departamento, provincia o distrito: todos tienen código y nombre."""

    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
