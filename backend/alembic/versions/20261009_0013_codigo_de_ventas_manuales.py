"""Código de pedido no adivinable para las ventas manuales.

Las ventas cargadas a mano usaban su número de venta (V-001…) como código de
pedido. Ese código es el que abre la consulta pública de un pedido, y siendo
correlativo cualquiera podía recorrerlos. Pasan a ECN-M-AAMMDD-NNNN, como los
de la web pero con la M de manual; el V-NNN queda en `correlativo`.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-09
"""

import random
from collections.abc import Sequence
from datetime import timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIMA = timezone(timedelta(hours=-5))


def upgrade() -> None:
    conexion = op.get_bind()
    usados = set(conexion.scalars(sa.text("SELECT numero_pedido FROM pedidos")))
    viejos = conexion.execute(
        sa.text(
            "SELECT id, creado_en FROM pedidos "
            "WHERE origen = 'manual' AND numero_pedido ~ '^V-[0-9]+$'"
        )
    ).all()
    for id_, creado_en in viejos:
        while True:
            codigo = (
                f"ECN-M-{creado_en.astimezone(LIMA):%y%m%d}-{random.randint(1000, 9999)}"
            )
            if codigo not in usados:
                break
        usados.add(codigo)
        conexion.execute(
            sa.text("UPDATE pedidos SET numero_pedido = :c WHERE id = :i"),
            {"c": codigo, "i": id_},
        )


def downgrade() -> None:
    op.execute(
        "UPDATE pedidos SET numero_pedido = 'V-' || lpad(correlativo::text, 3, '0') "
        "WHERE origen = 'manual' AND numero_pedido LIKE 'ECN-M-%'"
    )
