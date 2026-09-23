"""Configuración del backend. Todo sale de variables de entorno o de .env."""

from decimal import Decimal
from functools import lru_cache

from pydantic import field_validator
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
    # En el servidor se pone la dirección del sitio publicado, separando con
    # comas si hay más de una.
    origenes_cors: list[str] = [
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ]

    @field_validator("origenes_cors", mode="before")
    @classmethod
    def _separar_por_comas(cls, valor):
        """Permite ORIGENES_CORS=https://a.com,https://b.com en el entorno.

        Pydantic espera JSON para una lista, que es incómodo de escribir en el
        panel de un servidor; acá se acepta la forma corta.
        """
        if isinstance(valor, str) and not valor.strip().startswith("["):
            return [t.strip() for t in valor.split(",") if t.strip()]
        return valor

    @field_validator("database_url", mode="after")
    @classmethod
    def _con_psycopg(cls, valor: str) -> str:
        """Fuerza el driver psycopg en la URL de la base.

        Los servidores administrados entregan la URL como `postgresql://…`,
        que SQLAlchemy resuelve al driver viejo (psycopg2) y falla porque no
        está instalado. Se traduce acá y no en cada despliegue.
        """
        for prefijo in ("postgresql://", "postgres://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg://" + valor[len(prefijo):]
        return valor

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
