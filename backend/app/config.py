"""Configuración del backend. Todo sale de variables de entorno o de .env."""

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    proyecto: str = "El Chico Naturista API"
    version: str = "0.1.0"
    entorno: str = "desarrollo"

    # postgresql+psycopg://usuario:clave@host:puerto/base
    database_url: str = "postgresql+psycopg://ecn:ecn@localhost:5432/elchiconaturista"

    prefijo_api: str = "/api/v1"

    # Orígenes que pueden llamar a la API desde el navegador (Astro en dev).
    origenes_cors: list[str] = [
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ]

    # Regla de negocio duplicada intencionalmente con el frontend
    # (src/data/tienda.js → envioGratisDesde, src/alpine.js →
    # COSTO_ENVIO_LIMA). El backend es quien manda al crear un pedido: nunca
    # se confía en el envío/total que mande el cliente. Si se centraliza
    # algún día, que sea acá y se sirva al frontend por API.
    envio_costo_lima: Decimal = Decimal("12.00")
    envio_gratis_desde: Decimal = Decimal("120.00")


@lru_cache
def obtener_ajustes() -> Ajustes:
    """Una sola instancia por proceso; la cachea lru_cache."""
    return Ajustes()


ajustes = obtener_ajustes()
