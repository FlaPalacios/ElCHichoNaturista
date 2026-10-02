"""Papelera para marcas, categorías y subcategorías.

Borrar pasa a ser reversible: en vez de eliminar la fila se marca con la fecha
en `eliminado_en`, y el panel la muestra en una papelera desde donde se puede
restaurar o eliminar para siempre.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("marcas", "categorias", "subcategorias")


def upgrade() -> None:
    for tabla in TABLAS:
        op.add_column(
            tabla, sa.Column("eliminado_en", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    for tabla in TABLAS:
        op.drop_column(tabla, "eliminado_en")
