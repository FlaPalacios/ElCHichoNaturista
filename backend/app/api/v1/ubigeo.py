"""Departamentos, provincias y distritos del Perú (padrón INEI).

El checkout los pide en cascada: primero el departamento, luego sus provincias
y al final los distritos de esa provincia. Así el navegador nunca baja los 1891
distritos de golpe.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.models import Departamento, Distrito, Provincia
from app.schemas import LugarOut

router = APIRouter(prefix="/ubigeo", tags=["ubigeo"])


@router.get("/departamentos", response_model=list[LugarOut], summary="Los 25 departamentos")
def listar_departamentos(sesion: Annotated[Session, Depends(obtener_sesion)]):
    return sesion.scalars(select(Departamento).order_by(Departamento.nombre)).all()


@router.get(
    "/departamentos/{codigo}/provincias",
    response_model=list[LugarOut],
    summary="Provincias de un departamento",
    responses={404: {"description": "No existe ese departamento"}},
)
def listar_provincias(codigo: str, sesion: Annotated[Session, Depends(obtener_sesion)]):
    if sesion.get(Departamento, codigo) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento '{codigo}'.",
        )
    consulta = (
        select(Provincia)
        .where(Provincia.departamento_codigo == codigo)
        .order_by(Provincia.nombre)
    )
    return sesion.scalars(consulta).all()


@router.get(
    "/provincias/{codigo}/distritos",
    response_model=list[LugarOut],
    summary="Distritos de una provincia",
    responses={404: {"description": "No existe esa provincia"}},
)
def listar_distritos(codigo: str, sesion: Annotated[Session, Depends(obtener_sesion)]):
    if sesion.get(Provincia, codigo) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la provincia '{codigo}'.",
        )
    consulta = (
        select(Distrito)
        .where(Distrito.provincia_codigo == codigo)
        .order_by(Distrito.nombre)
    )
    return sesion.scalars(consulta).all()
