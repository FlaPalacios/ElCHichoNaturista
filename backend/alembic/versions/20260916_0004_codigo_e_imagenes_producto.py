"""Código de negocio del producto y sus imágenes de Cloudinary.

Añade `productos.codigo` (ECN-001), el identificador que usa Fernando en su
catálogo, y crea `product_images` para las varias fotos de cada producto.

Las imágenes se relacionan por `codigo` y no por `id` porque así vienen las
planillas del negocio: al recargar el catálogo los `id` pueden cambiar, el
código no.

De paso retira `productos.imagen_url`: nació cuando cada producto tenía una
sola foto y nunca llegó a usarse (se sembró siempre en null). La imagen
principal ahora es la de `orden` 1 en `product_images`.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable primero para poder rellenar las filas que ya existan; al final
    # se exige NOT NULL. Las filas viejas reciben un código derivado del id,
    # que el seed real reemplaza.
    op.add_column("productos", sa.Column("codigo", sa.String(length=10), nullable=True))
    op.execute("UPDATE productos SET codigo = 'ECN-' || lpad(id::text, 3, '0')")
    op.alter_column("productos", "codigo", nullable=False)
    op.create_unique_constraint("uq_productos_codigo", "productos", ["codigo"])

    op.create_table(
        "product_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_producto", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["id_producto"], ["productos.codigo"], ondelete="CASCADE", onupdate="CASCADE"
        ),
        # Orden 1 = imagen principal; no puede haber dos fotos en la misma
        # posición para un mismo producto.
        sa.UniqueConstraint("id_producto", "orden", name="uq_product_images_producto_orden"),
    )
    op.create_index("ix_product_images_id_producto", "product_images", ["id_producto"])

    op.drop_column("productos", "imagen_url")


def downgrade() -> None:
    op.add_column("productos", sa.Column("imagen_url", sa.Text(), nullable=True))

    op.drop_index("ix_product_images_id_producto", table_name="product_images")
    op.drop_table("product_images")

    op.drop_constraint("uq_productos_codigo", "productos", type_="unique")
    op.drop_column("productos", "codigo")
