"""GET /api/v1/tienda — los datos de la tienda que el sitio necesita pintar.

Número de WhatsApp, dirección, redes, avisos del cintillo y el monto desde el
que el envío es gratis. Todo editable desde el panel, así cambiarlos no obliga
a recompilar el sitio.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import tienda as ajustes_tienda
from app.database import obtener_sesion

router = APIRouter(prefix="/tienda", tags=["tienda"])


class TiendaOut(BaseModel):
    nombre: str
    lema: str
    whatsapp: str
    whatsapp_visible: str
    correo: str
    direccion: str
    horario: str
    tiktok: str
    linkedin: str
    metodos_pago: str
    plantilla_whatsapp: str
    avisos: list[str]
    mostrar_agotado: bool
    envio_gratis_desde: Decimal


@router.get("", response_model=TiendaOut, summary="Datos y avisos de la tienda")
def leer_tienda(sesion: Annotated[Session, Depends(obtener_sesion)]):
    valores = ajustes_tienda.leer_todo(sesion)
    return TiendaOut(
        **{k: v for k, v in valores.items() if k not in ("avisos", "envio_gratis_desde", "stock_bajo", "mostrar_agotado")},
        mostrar_agotado=ajustes_tienda.si_no(sesion, "mostrar_agotado"),
        avisos=[linea for linea in valores["avisos"].split("\n") if linea.strip()],
        envio_gratis_desde=ajustes_tienda.numero(sesion, "envio_gratis_desde"),
    )
