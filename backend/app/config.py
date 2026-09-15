"""Configuración del backend. Todo sale de variables de entorno o de .env."""

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


@lru_cache
def obtener_ajustes() -> Ajustes:
    """Una sola instancia por proceso; la cachea lru_cache."""
    return Ajustes()


ajustes = obtener_ajustes()
