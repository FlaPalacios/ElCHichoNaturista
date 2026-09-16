"""Datos del checkout en el pedido.

Añade a `pedidos` los campos que el formulario de checkout ya recoge y que
hasta ahora solo vivían en el navegador: distrito, referencia de entrega,
correo de contacto, nota y método de pago.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# create_type=False: igual que estado_pedido en la migración 0001. Sin esto,
# Alembic podría intentar crear el tipo una segunda vez.
METODO_PAGO = postgresql.ENUM(
    "yape",
    "transferencia",
    "contraentrega",
    name="metodo_pago_pedido",
    create_type=False,
)


def upgrade() -> None:
    METODO_PAGO.create(op.get_bind(), checkfirst=True)

    op.add_column("pedidos", sa.Column("distrito", sa.String(length=100), nullable=True))
    op.add_column("pedidos", sa.Column("referencia", sa.Text(), nullable=True))
    op.add_column("pedidos", sa.Column("email_contacto", sa.String(length=150), nullable=True))
    op.add_column("pedidos", sa.Column("nota", sa.Text(), nullable=True))
    op.add_column("pedidos", sa.Column("metodo_pago", METODO_PAGO, nullable=True))


def downgrade() -> None:
    op.drop_column("pedidos", "metodo_pago")
    op.drop_column("pedidos", "nota")
    op.drop_column("pedidos", "email_contacto")
    op.drop_column("pedidos", "referencia")
    op.drop_column("pedidos", "distrito")

    METODO_PAGO.drop(op.get_bind(), checkfirst=True)
