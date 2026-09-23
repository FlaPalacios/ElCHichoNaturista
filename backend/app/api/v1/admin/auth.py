"""POST /api/v1/admin/login — entrada al panel."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import ajustes
from app.database import obtener_sesion
from app.models import Admin
from app.seguridad import admin_actual, autenticar, crear_token

router = APIRouter(tags=["admin"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_horas: int


class AdminOut(BaseModel):
    usuario: str


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Entra al panel y devuelve el token",
    responses={401: {"description": "Usuario o contraseña incorrectos"}},
)
def login(
    datos: Annotated[OAuth2PasswordRequestForm, Depends()],
    sesion: Annotated[Session, Depends(obtener_sesion)],
):
    admin = autenticar(sesion, datos.username, datos.password)
    if admin is None:
        # Mismo mensaje para usuario inexistente y clave mala: no le decimos a
        # nadie si acertó el usuario.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(
        access_token=crear_token(admin.usuario), expira_en_horas=ajustes.jwt_horas
    )


@router.get("/yo", response_model=AdminOut, summary="Comprueba que el token sirve")
def yo(admin: Annotated[Admin, Depends(admin_actual)]):
    return AdminOut(usuario=admin.usuario)
