"""Marcas y subcategorías: el catálogo pasa a tener dos niveles.

Antes había una sola lista plana de categorías. Ahora el negocio organiza su
catálogo en categoría (Frescos, Abarrotes, Cuidado Personal) → subcategoría, y
además por marca (Green House / HIRI, Henna Colors, Fit Rex, Algarrobos
Orgánicos).

`productos.categoria_id` desaparece: la categoría de un producto es la de su
subcategoría, así no pueden contradecirse. `productos.origen` también se va:
sus valores eran justamente las marcas.

**Esta migración vacía el catálogo.** Categorías, productos e imágenes se
vuelven a cargar desde las planillas de `app/datos` con `python -m app.seed`,
que es su fuente de verdad. Se detiene si hay pedidos que dependan de algún
producto.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conexion = op.get_bind()

    if conexion.execute(sa.text("SELECT 1 FROM pedido_items LIMIT 1")).first():
        raise RuntimeError(
            "Hay pedidos con items: esta migración vacía el catálogo y esos "
            "productos están referenciados. Respáldalos antes de continuar."
        )

    # El catálogo se reconstruye desde las planillas; las imágenes caen solas
    # por la FK en cascada sobre productos.codigo.
    conexion.execute(sa.text("DELETE FROM productos"))
    conexion.execute(sa.text("DELETE FROM categorias"))

    op.create_table(
        "marcas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_marcas_slug"),
    )

    op.add_column(
        "categorias",
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "subcategorias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        # Slug único en toda la tienda: así la URL /catalogo?subcategoria=x
        # no necesita saber de qué categoría cuelga.
        sa.UniqueConstraint("slug", name="uq_subcategorias_slug"),
        sa.ForeignKeyConstraint(
            ["categoria_id"], ["categorias.id"], ondelete="RESTRICT",
            name="fk_subcategorias_categoria_id",
        ),
    )
    op.create_index("ix_subcategorias_categoria_id", "subcategorias", ["categoria_id"])

    op.drop_index("ix_productos_categoria_id", table_name="productos")
    op.drop_constraint("fk_productos_categoria_id", "productos", type_="foreignkey")
    op.drop_column("productos", "categoria_id")
    op.drop_column("productos", "origen")

    op.add_column("productos", sa.Column("marca_id", sa.Integer(), nullable=False))
    op.add_column("productos", sa.Column("subcategoria_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "fk_productos_marca_id", "productos", "marcas", ["marca_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_productos_subcategoria_id", "productos", "subcategorias",
        ["subcategoria_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_productos_marca_id", "productos", ["marca_id"])
    op.create_index("ix_productos_subcategoria_id", "productos", ["subcategoria_id"])


def downgrade() -> None:
    conexion = op.get_bind()
    conexion.execute(sa.text("DELETE FROM productos"))

    op.drop_index("ix_productos_subcategoria_id", table_name="productos")
    op.drop_index("ix_productos_marca_id", table_name="productos")
    op.drop_constraint("fk_productos_subcategoria_id", "productos", type_="foreignkey")
    op.drop_constraint("fk_productos_marca_id", "productos", type_="foreignkey")
    op.drop_column("productos", "subcategoria_id")
    op.drop_column("productos", "marca_id")

    op.add_column("productos", sa.Column("origen", sa.String(length=150), nullable=True))
    op.add_column("productos", sa.Column("categoria_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "fk_productos_categoria_id", "productos", "categorias", ["categoria_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_productos_categoria_id", "productos", ["categoria_id"])

    op.drop_index("ix_subcategorias_categoria_id", table_name="subcategorias")
    op.drop_table("subcategorias")
    op.drop_column("categorias", "activo")
    op.drop_table("marcas")
