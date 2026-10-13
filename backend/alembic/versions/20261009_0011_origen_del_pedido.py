"""Origen del pedido y contacto opcional.

`origen` distingue los pedidos hechos en la web de las ventas registradas a
mano (las que hubo antes de la web, o las que se cierran por fuera). Una venta
manual puede no tener teléfono ni dirección, así que esas columnas pasan a
aceptar null; los pedidos de la web los siguen exigiendo en el checkout.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pedidos",
        sa.Column("origen", sa.String(10), nullable=False, server_default="web"),
    )
    op.create_check_constraint(
        "ck_pedidos_origen", "pedidos", "origen IN ('web', 'manual')"
    )
    op.alter_column("pedidos", "telefono_contacto", nullable=True)
    op.alter_column("pedidos", "direccion_envio", nullable=True)


def downgrade() -> None:
    # Las ventas manuales sin contacto no caben en el esquema anterior.
    op.execute("UPDATE pedidos SET telefono_contacto = '' WHERE telefono_contacto IS NULL")
    op.execute("UPDATE pedidos SET direccion_envio = '' WHERE direccion_envio IS NULL")
    op.alter_column("pedidos", "direccion_envio", nullable=False)
    op.alter_column("pedidos", "telefono_contacto", nullable=False)
    op.drop_constraint("ck_pedidos_origen", "pedidos", type_="check")
    op.drop_column("pedidos", "origen")
