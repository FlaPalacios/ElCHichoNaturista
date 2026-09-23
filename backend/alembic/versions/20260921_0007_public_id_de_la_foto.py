"""Guarda el identificador que Cloudinary le da a cada foto.

Sin esto, borrar una foto obliga a adivinar su `public_id` a partir de la URL.
Las fotos que entraron por planilla se quedan con el campo vacío y se siguen
deduciendo de la URL (ver `app/fotos.py`); las que se suban desde el panel lo
traen anotado.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_images", sa.Column("public_id", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("product_images", "public_id")
