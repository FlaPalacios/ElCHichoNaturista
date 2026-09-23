"""Ajustes de la tienda y tarifas de envío, desde el panel."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tienda
from app.database import obtener_sesion
from app.models import Admin, Departamento, Provincia, TarifaEnvio
from app.seguridad import admin_actual

router = APIRouter(tags=["admin"])


class Ajuste(BaseModel):
    clave: str
    valor: str
    tipo: str


class TarifaOut(BaseModel):
    id: int
    departamento_codigo: str
    departamento: str
    provincia_codigo: str | None = None
    provincia: str | None = None
    costo: Decimal


class TarifaCambio(BaseModel):
    costo: Decimal = Field(ge=0, le=999)


@router.get("/configuracion", response_model=list[Ajuste], summary="Los ajustes de la tienda")
def leer_configuracion(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    valores = tienda.leer_todo(sesion)
    return [
        Ajuste(clave=clave, valor=valores[clave], tipo=tipo)
        for clave, (_, tipo) in tienda.AJUSTES.items()
    ]


@router.put(
    "/configuracion", response_model=list[Ajuste], summary="Guarda los ajustes"
)
def guardar_configuracion(
    valores: dict[str, str],
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    tienda.guardar(sesion, valores)
    sesion.commit()
    return leer_configuracion(sesion, admin)


@router.get("/tarifas", response_model=list[TarifaOut], summary="Costos de envío por zona")
def listar_tarifas(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    consulta = (
        select(TarifaEnvio, Departamento.nombre, Provincia.nombre)
        .join(Departamento, Departamento.codigo == TarifaEnvio.departamento_codigo)
        .outerjoin(Provincia, Provincia.codigo == TarifaEnvio.provincia_codigo)
        .order_by(Departamento.nombre, Provincia.nombre.nullsfirst())
    )
    return [
        TarifaOut(
            id=t.id,
            departamento_codigo=t.departamento_codigo,
            departamento=departamento,
            provincia_codigo=t.provincia_codigo,
            provincia=provincia,
            costo=t.costo,
        )
        for t, departamento, provincia in sesion.execute(consulta).all()
    ]


@router.patch(
    "/tarifas/{tarifa_id}",
    response_model=TarifaOut,
    summary="Cambia el costo de una zona",
)
def cambiar_tarifa(
    tarifa_id: int,
    cambio: TarifaCambio,
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
):
    tarifa = sesion.get(TarifaEnvio, tarifa_id)
    if tarifa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa tarifa.")
    tarifa.costo = cambio.costo
    sesion.commit()
    return next(t for t in listar_tarifas(sesion, admin) if t.id == tarifa_id)
