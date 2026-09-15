"""Esquema inicial completo: catálogo, clientes, pedidos y admin.

El modelo de datos se crea de una sola vez aunque los endpoints se construyan
por etapas (ver CONTEXTO_PROYECTO-post-fase2.md).

Revision ID: 0001
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# El tipo se crea y se borra a mano para que el downgrade quede limpio.
estado_pedido = postgresql.ENUM(
    "pendiente",
    "coordinado",
    "enviado",
    "completado",
    "cancelado",
    name="estado_pedido",
    create_type=False,
)


def upgrade() -> None:
    estado_pedido.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_categorias_slug"),
    )
    op.create_index("ix_categorias_slug", "categorias", ["slug"])

    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("descripcion_corta", sa.Text(), nullable=True),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("precio", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("imagen_url", sa.Text(), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("destacado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["categoria_id"],
            ["categorias.id"],
            name="fk_productos_categoria_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_productos_slug"),
    )
    op.create_index("ix_productos_slug", "productos", ["slug"])
    op.create_index("ix_productos_categoria_id", "productos", ["categoria_id"])
    op.create_index("ix_productos_activo", "productos", ["activo"])

    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_clientes_email"),
    )
    op.create_index("ix_clientes_email", "clientes", ["email"])

    op.create_table(
        "pedidos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero_pedido", sa.String(length=20), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("nombre_contacto", sa.String(length=150), nullable=False),
        sa.Column("telefono_contacto", sa.String(length=20), nullable=False),
        sa.Column("direccion_envio", sa.Text(), nullable=True),
        sa.Column("departamento", sa.String(length=100), nullable=True),
        sa.Column(
            "estado",
            estado_pedido,
            nullable=False,
            server_default="pendiente",
        ),
        sa.Column("total", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["cliente_id"],
            ["clientes.id"],
            name="fk_pedidos_cliente_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_pedido", name="uq_pedidos_numero_pedido"),
    )
    op.create_index("ix_pedidos_numero_pedido", "pedidos", ["numero_pedido"])

    op.create_table(
        "pedido_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["pedido_id"],
            ["pedidos.id"],
            name="fk_pedido_items_pedido_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["producto_id"],
            ["productos.id"],
            name="fk_pedido_items_producto_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pedido_items_pedido_id", "pedido_items", ["pedido_id"])
    op.create_index("ix_pedido_items_producto_id", "pedido_items", ["producto_id"])

    op.create_table(
        "admin",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario", name="uq_admin_usuario"),
    )
    op.create_index("ix_admin_usuario", "admin", ["usuario"])


def downgrade() -> None:
    op.drop_index("ix_admin_usuario", table_name="admin")
    op.drop_table("admin")

    op.drop_index("ix_pedido_items_producto_id", table_name="pedido_items")
    op.drop_index("ix_pedido_items_pedido_id", table_name="pedido_items")
    op.drop_table("pedido_items")

    op.drop_index("ix_pedidos_numero_pedido", table_name="pedidos")
    op.drop_table("pedidos")

    op.drop_index("ix_clientes_email", table_name="clientes")
    op.drop_table("clientes")

    op.drop_index("ix_productos_activo", table_name="productos")
    op.drop_index("ix_productos_categoria_id", table_name="productos")
    op.drop_index("ix_productos_slug", table_name="productos")
    op.drop_table("productos")

    op.drop_index("ix_categorias_slug", table_name="categorias")
    op.drop_table("categorias")

    estado_pedido.drop(op.get_bind(), checkfirst=True)
