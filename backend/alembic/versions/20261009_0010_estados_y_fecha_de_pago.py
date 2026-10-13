"""Estados del pedido más simples y fecha de pago.

Los siete estados de la 0006 pasan a cinco, los mismos que usa el Google Sheet
de costos: pendiente, pagado, enviado, completado y cancelado. `fecha_pago` es
el día en que entró el dinero y lo que usa el Sheet para la caja.

Equivalencias: nuevo → pendiente; pago_confirmado y preparando → pagado;
entregado → completado; no_concretado → cancelado. En los pedidos que ya estaban
pagados se copia la fecha del pedido como fecha de pago, que es lo más cercano
que se sabe; se corrige a mano desde el panel si hace falta.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADOS_NUEVOS = ("pendiente", "pagado", "enviado", "completado", "cancelado")
ESTADOS_ANTERIORES = (
    "nuevo",
    "pago_confirmado",
    "preparando",
    "enviado",
    "entregado",
    "cancelado",
    "no_concretado",
)

IDA = {
    "nuevo": "pendiente",
    "pago_confirmado": "pagado",
    "preparando": "pagado",
    "enviado": "enviado",
    "entregado": "completado",
    "cancelado": "cancelado",
    "no_concretado": "cancelado",
}
VUELTA = {
    "pendiente": "nuevo",
    "pagado": "pago_confirmado",
    "enviado": "enviado",
    "completado": "entregado",
    "cancelado": "cancelado",
}


def _cambiar_estados(tipo_temporal: str, valores: tuple, equivalencias: dict, defecto: str):
    tipo = postgresql.ENUM(*valores, name=tipo_temporal)
    tipo.create(op.get_bind(), checkfirst=True)
    casos = " ".join(f"WHEN '{a}' THEN '{b}'" for a, b in equivalencias.items())
    op.execute("ALTER TABLE pedidos ALTER COLUMN estado DROP DEFAULT")
    op.execute(
        f"ALTER TABLE pedidos ALTER COLUMN estado TYPE {tipo_temporal} "
        f"USING (CASE estado::text {casos} ELSE '{defecto}' END)::{tipo_temporal}"
    )
    op.execute(f"ALTER TABLE pedidos ALTER COLUMN estado SET DEFAULT '{defecto}'")
    op.execute("DROP TYPE estado_pedido")
    op.execute(f"ALTER TYPE {tipo_temporal} RENAME TO estado_pedido")


def upgrade() -> None:
    op.add_column(
        "pedidos", sa.Column("fecha_pago", sa.DateTime(timezone=True), nullable=True)
    )
    # Antes del cambio de tipo, mientras se sabe cuáles estaban pagados.
    op.execute(
        "UPDATE pedidos SET fecha_pago = creado_en "
        "WHERE estado::text IN ('pago_confirmado', 'preparando', 'enviado', 'entregado')"
    )
    _cambiar_estados("estado_pedido_v3", ESTADOS_NUEVOS, IDA, "pendiente")


def downgrade() -> None:
    _cambiar_estados("estado_pedido_v2", ESTADOS_ANTERIORES, VUELTA, "nuevo")
    op.drop_column("pedidos", "fecha_pago")
