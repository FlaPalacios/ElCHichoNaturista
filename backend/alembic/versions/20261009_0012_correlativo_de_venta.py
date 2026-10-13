"""Número de venta correlativo (V-001, V-002…) para todos los pedidos.

`numero_pedido` sigue siendo el código que ve el cliente (ECN-AAMMDD-NNNN en
los pedidos de la web). `correlativo` es la numeración interna que comparten
la web y el Google Sheet: continúa la de las ventas anteriores a la web.

Las ventas manuales que ya se llaman V-NNN conservan ese número; el resto se
numera después, en orden de fecha.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECUENCIA = "pedidos_correlativo_seq"


def upgrade() -> None:
    op.execute(f"CREATE SEQUENCE {SECUENCIA}")
    op.add_column("pedidos", sa.Column("correlativo", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE pedidos SET correlativo = substring(numero_pedido from 3)::int "
        "WHERE numero_pedido ~ '^V-[0-9]+$'"
    )
    op.execute(
        """
        WITH base AS (SELECT coalesce(max(correlativo), 0) AS n FROM pedidos),
        resto AS (
            SELECT id, row_number() OVER (ORDER BY creado_en, numero_pedido) AS fila
            FROM pedidos WHERE correlativo IS NULL
        )
        UPDATE pedidos p SET correlativo = base.n + resto.fila
        FROM base, resto WHERE p.id = resto.id
        """
    )
    # El próximo pedido sigue desde el último número usado.
    op.execute(
        f"SELECT setval('{SECUENCIA}', coalesce((SELECT max(correlativo) FROM pedidos), 0) + 1, false)"
    )

    op.alter_column(
        "pedidos",
        "correlativo",
        nullable=False,
        server_default=sa.text(f"nextval('{SECUENCIA}')"),
    )
    op.execute(f"ALTER SEQUENCE {SECUENCIA} OWNED BY pedidos.correlativo")
    op.create_unique_constraint("uq_pedidos_correlativo", "pedidos", ["correlativo"])


def downgrade() -> None:
    op.drop_constraint("uq_pedidos_correlativo", "pedidos", type_="unique")
    op.drop_column("pedidos", "correlativo")  # la secuencia se va con la columna
