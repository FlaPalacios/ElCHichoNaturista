"""Ajustes de la tienda editables desde el panel.

Hasta ahora el número de WhatsApp, la dirección, las redes y el umbral de stock
bajo vivían escritos en el código (`src/data/tienda.js` y `app/config.py`).
Pasan a una tabla de clave-valor para que Fernando los cambie sin tocar nada.

Es clave-valor y no una tabla con una columna por ajuste porque la lista va a
seguir creciendo, y así agregar uno no obliga a una migración.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "configuracion",
        sa.Column("clave", sa.String(length=60), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("clave"),
    )


def downgrade() -> None:
    op.drop_table("configuracion")
