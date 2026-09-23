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

    # Panel de administración. El secreto se genera al instalar y va en .env;
    # si cambia, todas las sesiones abiertas se caen.
    jwt_secreto: str = "cambiame-en-el-env"
    jwt_algoritmo: str = "HS256"
    jwt_horas: int = 12

    # Solo los lee `python -m app.crear_admin` para sembrar el usuario.
    admin_usuario: str = "NatuAdmin"
    admin_password: str = ""

    # Cloudinary: subida de fotos desde el panel.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    @property
    def cloudinary_configurado(self) -> bool:
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )

    # Desde cuántas unidades se considera que a un producto le queda poco.
    # Se podrá editar desde Configuración (etapa 6).
    stock_bajo: int = 5

    # El costo del envío sale de la tabla `tarifas_envio`, por departamento.
    # Acá solo queda el monto desde el que el envío es gratis, que es una
    # promesa de toda la tienda y no depende del destino.
    envio_gratis_desde: Decimal = Decimal("120.00")


@lru_cache
def obtener_ajustes() -> Ajustes:
    """Una sola instancia por proceso; la cachea lru_cache."""
    return Ajustes()


ajustes = obtener_ajustes()
