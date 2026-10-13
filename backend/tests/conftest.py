"""Fixtures de las pruebas.

Usan la misma base de PostgreSQL del desarrollo pero dentro de un esquema
temporal que se crea al empezar y se borra al terminar, así no tocan los datos
reales y no hace falta permiso para crear bases.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import ajustes
from app.database import Base
from app.models import Categoria, Marca, Subcategoria


@pytest.fixture(scope="session")
def motor():
    esquema = f"test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(ajustes.database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as con:
        con.execute(text(f'CREATE SCHEMA "{esquema}"'))
    motor = create_engine(
        ajustes.database_url, connect_args={"options": f"-csearch_path={esquema}"}
    )
    Base.metadata.create_all(motor)
    yield motor
    motor.dispose()
    with admin.connect() as con:
        con.execute(text(f'DROP SCHEMA "{esquema}" CASCADE'))
    admin.dispose()


@pytest.fixture()
def sesion(motor):
    """Una sesión limpia por prueba: se vacían las tablas al terminar."""
    with Session(motor) as s:
        yield s
        s.rollback()
    with motor.begin() as con:
        tablas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        con.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def catalogo_base(sesion):
    """Una marca y una subcategoría, lo mínimo para tener productos."""
    cat = Categoria(nombre="Abarrotes", slug="abarrotes")
    sesion.add_all([cat, Marca(nombre="Marca Uno", slug="marca-uno")])
    sesion.flush()
    sesion.add(Subcategoria(nombre="Mieles", slug="mieles", categoria_id=cat.id))
    sesion.commit()
