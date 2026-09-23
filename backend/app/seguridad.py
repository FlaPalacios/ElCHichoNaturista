"""Contraseñas y tokens del panel de administración.

Hay un solo administrador (Fernando), sin roles ni permisos: quien tiene un
token válido puede hacer todo lo del panel.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ajustes
from app.database import obtener_sesion
from app.models import Admin

# tokenUrl es solo para el botón "Authorize" de /docs.
esquema_token = OAuth2PasswordBearer(tokenUrl=f"{ajustes.prefijo_api}/admin/login")

NO_AUTORIZADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sesión no válida o vencida.",
    headers={"WWW-Authenticate": "Bearer"},
)


def hashear(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar(password: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hash_guardado.encode())
    except ValueError:
        # El hash guardado está corrupto o no es bcrypt: no es una sesión válida.
        return False


def crear_token(usuario: str) -> str:
    ahora = datetime.now(timezone.utc)
    carga = {
        "sub": usuario,
        "iat": ahora,
        "exp": ahora + timedelta(hours=ajustes.jwt_horas),
    }
    return jwt.encode(carga, ajustes.jwt_secreto, algorithm=ajustes.jwt_algoritmo)


def autenticar(sesion: Session, usuario: str, password: str) -> Admin | None:
    admin = sesion.scalar(select(Admin).where(Admin.usuario == usuario))
    if admin is None or not verificar(password, admin.password_hash):
        return None
    return admin


def admin_actual(
    token: Annotated[str, Depends(esquema_token)],
    sesion: Annotated[Session, Depends(obtener_sesion)],
) -> Admin:
    """Dependencia que protege las rutas del panel."""
    try:
        carga = jwt.decode(
            token, ajustes.jwt_secreto, algorithms=[ajustes.jwt_algoritmo]
        )
    except jwt.PyJWTError as error:
        raise NO_AUTORIZADO from error

    usuario = carga.get("sub")
    admin = (
        sesion.scalar(select(Admin).where(Admin.usuario == usuario)) if usuario else None
    )
    if admin is None:
        # El token es válido pero el usuario ya no existe.
        raise NO_AUTORIZADO
    return admin
