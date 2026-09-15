"""Esquemas Pydantic: la forma en que la API entrega los datos."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
