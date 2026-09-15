"""Motor de SQLAlchemy, sesiones y la base declarativa."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import ajustes

motor = create_engine(
    ajustes.database_url,
    pool_pre_ping=True,  # descarta conexiones muertas antes de usarlas
    echo=False,
)

SesionLocal = sessionmaker(bind=motor, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base declarativa de la que heredan todos los modelos."""


def obtener_sesion() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesión por request, cerrada al terminar."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
