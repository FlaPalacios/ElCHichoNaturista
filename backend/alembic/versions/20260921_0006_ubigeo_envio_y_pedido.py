"""Ubigeo del Perú, tarifas de envío y el pedido rehecho.

Tres cambios que van juntos porque se tocan entre sí:

1. **Ubigeo**: departamentos → provincias → distritos, con los datos del INEI
   2022. El checkout deja de tener una lista de 17 distritos de Lima escrita a
   mano y pasa a cubrir todo el Perú.

2. **Tarifas de envío**: una fila por departamento, con la posibilidad de
   afinar por provincia. Hoy: S/ 10 en la provincia de Lima y en el Callao,
   S/ 15 en el resto del país; gratis desde cierto monto. Editable desde el
   panel (etapa 6) sin tocar código.

3. **Pedido**: se quita el recojo en tienda (todo es delivery) y el método de
   pago (ahora es texto informativo: Yape, Plin o transferencia). Se guarda a
   dónde va el pedido (departamento, provincia, distrito) y lo que el panel
   necesita para seguirlo: estados nuevos, courier, código de seguimiento y
   nota interna.

Los estados pasan de (pendiente, coordinado, enviado, completado, cancelado) a
(nuevo, pago_confirmado, preparando, enviado, entregado, cancelado,
no_concretado).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADOS_NUEVOS = (
    "nuevo",
    "pago_confirmado",
    "preparando",
    "enviado",
    "entregado",
    "cancelado",
    "no_concretado",
)
ESTADOS_VIEJOS = ("pendiente", "coordinado", "enviado", "completado", "cancelado")

# Cómo se traduce un pedido que ya existía al vocabulario nuevo.
EQUIVALENCIAS = {
    "pendiente": "nuevo",
    "coordinado": "pago_confirmado",
    "enviado": "enviado",
    "completado": "entregado",
    "cancelado": "cancelado",
}


def upgrade() -> None:
    # ── Ubigeo ───────────────────────────────────────────────────────
    op.create_table(
        "departamentos",
        sa.Column("codigo", sa.String(length=2), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )
    op.create_table(
        "provincias",
        sa.Column("codigo", sa.String(length=4), nullable=False),
        sa.Column("departamento_codigo", sa.String(length=2), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
        sa.ForeignKeyConstraint(
            ["departamento_codigo"], ["departamentos.codigo"], ondelete="CASCADE",
            name="fk_provincias_departamento",
        ),
    )
    op.create_index("ix_provincias_departamento", "provincias", ["departamento_codigo"])

    op.create_table(
        "distritos",
        sa.Column("codigo", sa.String(length=6), nullable=False),
        sa.Column("provincia_codigo", sa.String(length=4), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
        sa.ForeignKeyConstraint(
            ["provincia_codigo"], ["provincias.codigo"], ondelete="CASCADE",
            name="fk_distritos_provincia",
        ),
    )
    op.create_index("ix_distritos_provincia", "distritos", ["provincia_codigo"])

    # ── Tarifas de envío ─────────────────────────────────────────────
    op.create_table(
        "tarifas_envio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("departamento_codigo", sa.String(length=2), nullable=False),
        # Null = tarifa base del departamento. Con valor = afina esa provincia,
        # que es como Lima cobra distinto en la capital que en Cañete.
        sa.Column("provincia_codigo", sa.String(length=4), nullable=True),
        sa.Column("costo", sa.Numeric(10, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["departamento_codigo"], ["departamentos.codigo"], ondelete="CASCADE",
            name="fk_tarifas_departamento",
        ),
        sa.ForeignKeyConstraint(
            ["provincia_codigo"], ["provincias.codigo"], ondelete="CASCADE",
            name="fk_tarifas_provincia",
        ),
        sa.UniqueConstraint(
            "departamento_codigo", "provincia_codigo", name="uq_tarifas_envio_zona"
        ),
    )

    # ── Pedido ───────────────────────────────────────────────────────
    estado_nuevo = postgresql.ENUM(*ESTADOS_NUEVOS, name="estado_pedido_v2")
    estado_nuevo.create(op.get_bind(), checkfirst=True)

    casos = " ".join(
        f"WHEN '{viejo}' THEN '{nuevo}'" for viejo, nuevo in EQUIVALENCIAS.items()
    )
    op.execute("ALTER TABLE pedidos ALTER COLUMN estado DROP DEFAULT")
    op.execute(
        "ALTER TABLE pedidos ALTER COLUMN estado TYPE estado_pedido_v2 "
        f"USING (CASE estado::text {casos} ELSE 'nuevo' END)::estado_pedido_v2"
    )
    op.execute("ALTER TABLE pedidos ALTER COLUMN estado SET DEFAULT 'nuevo'")
    op.execute("DROP TYPE estado_pedido")
    op.execute("ALTER TYPE estado_pedido_v2 RENAME TO estado_pedido")

    op.drop_column("pedidos", "metodo_pago")
    op.execute("DROP TYPE metodo_pago_pedido")

    op.add_column("pedidos", sa.Column("provincia", sa.String(length=100), nullable=True))
    # Código INEI del distrito: sin FK a propósito, para que el pedido conserve
    # su dirección aunque mañana se recargue la tabla de ubigeo.
    op.add_column("pedidos", sa.Column("ubigeo", sa.String(length=6), nullable=True))
    op.add_column(
        "pedidos",
        sa.Column("envio", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column("pedidos", sa.Column("courier", sa.String(length=100), nullable=True))
    op.add_column(
        "pedidos", sa.Column("codigo_seguimiento", sa.String(length=100), nullable=True)
    )
    op.add_column("pedidos", sa.Column("nota_interna", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pedidos", "nota_interna")
    op.drop_column("pedidos", "codigo_seguimiento")
    op.drop_column("pedidos", "courier")
    op.drop_column("pedidos", "envio")
    op.drop_column("pedidos", "ubigeo")
    op.drop_column("pedidos", "provincia")

    metodo_pago = postgresql.ENUM(
        "yape", "transferencia", "contraentrega", name="metodo_pago_pedido"
    )
    metodo_pago.create(op.get_bind(), checkfirst=True)
    op.add_column("pedidos", sa.Column("metodo_pago", metodo_pago, nullable=True))

    estado_viejo = postgresql.ENUM(*ESTADOS_VIEJOS, name="estado_pedido_v1")
    estado_viejo.create(op.get_bind(), checkfirst=True)
    inverso = {
        "nuevo": "pendiente",
        "pago_confirmado": "coordinado",
        "preparando": "coordinado",
        "enviado": "enviado",
        "entregado": "completado",
        "cancelado": "cancelado",
        "no_concretado": "cancelado",
    }
    casos = " ".join(f"WHEN '{n}' THEN '{v}'" for n, v in inverso.items())
    op.execute("ALTER TABLE pedidos ALTER COLUMN estado DROP DEFAULT")
    op.execute(
        "ALTER TABLE pedidos ALTER COLUMN estado TYPE estado_pedido_v1 "
        f"USING (CASE estado::text {casos} ELSE 'pendiente' END)::estado_pedido_v1"
    )
    op.execute("ALTER TABLE pedidos ALTER COLUMN estado SET DEFAULT 'pendiente'")
    op.execute("DROP TYPE estado_pedido")
    op.execute("ALTER TYPE estado_pedido_v1 RENAME TO estado_pedido")

    op.drop_table("tarifas_envio")
    op.drop_index("ix_distritos_provincia", table_name="distritos")
    op.drop_table("distritos")
    op.drop_index("ix_provincias_departamento", table_name="provincias")
    op.drop_table("provincias")
    op.drop_table("departamentos")
