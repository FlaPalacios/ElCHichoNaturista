"""Crea o actualiza el usuario del panel.

    python -m app.crear_admin

Lee `ADMIN_USUARIO` y `ADMIN_PASSWORD` del `.env` y guarda la contraseña
hasheada. La contraseña en claro nunca se escribe en la base ni en el código;
si la cambias en el `.env`, vuelve a correr este comando.
"""

from sqlalchemy import select

from app.config import ajustes
from app.database import SesionLocal
from app.models import Admin
from app.seguridad import hashear


def main() -> None:
    if not ajustes.admin_password:
        raise SystemExit(
            "Falta ADMIN_PASSWORD en el .env: sin eso no se puede crear el usuario."
        )

    with SesionLocal() as sesion:
        admin = sesion.scalar(
            select(Admin).where(Admin.usuario == ajustes.admin_usuario)
        )
        if admin is None:
            admin = Admin(usuario=ajustes.admin_usuario)
            sesion.add(admin)
            accion = "creado"
        else:
            accion = "actualizado"

        admin.password_hash = hashear(ajustes.admin_password)
        sesion.commit()

    print(f"Usuario '{ajustes.admin_usuario}' {accion}.")


if __name__ == "__main__":
    main()
