"""Contenido de la ficha de producto.

Añade a `productos` los campos que el frontend ya mostraba con datos de prueba:
presentación, origen, descripción larga, modo de uso, beneficios, precio
anterior (oferta) y la marca de más vendido.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("productos", sa.Column("presentacion", sa.String(length=120), nullable=True))
    op.add_column("productos", sa.Column("origen", sa.String(length=150), nullable=True))
    op.add_column("productos", sa.Column("descripcion_larga", sa.Text(), nullable=True))
    op.add_column("productos", sa.Column("modo_uso", sa.Text(), nullable=True))
    op.add_column(
        "productos",
        sa.Column(
            "beneficios",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column(
        "productos",
        sa.Column("precio_antes", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "productos",
        sa.Column(
            "mas_vendido", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )

    # El precio tachado tiene que ser mayor que el vigente, o no es oferta.
    op.create_check_constraint(
        "ck_productos_precio_antes_mayor",
        "productos",
        "precio_antes IS NULL OR precio_antes > precio",
    )

    op.create_index("ix_productos_mas_vendido", "productos", ["mas_vendido"])


def downgrade() -> None:
    op.drop_index("ix_productos_mas_vendido", table_name="productos")
    op.drop_constraint("ck_productos_precio_antes_mayor", "productos", type_="check")
    op.drop_column("productos", "mas_vendido")
    op.drop_column("productos", "precio_antes")
    op.drop_column("productos", "beneficios")
    op.drop_column("productos", "modo_uso")
    op.drop_column("productos", "descripcion_larga")
    op.drop_column("productos", "origen")
    op.drop_column("productos", "presentacion")
