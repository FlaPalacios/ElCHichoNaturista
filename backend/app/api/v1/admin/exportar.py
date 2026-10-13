"""Descargas para el Google Sheet de costos."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import exportar
from app.database import obtener_sesion
from app.models import Admin
from app.seguridad import admin_actual

router = APIRouter(prefix="/export", tags=["admin"])


@router.get(
    "/pedidos.csv",
    summary="Historial de pedidos en CSV para el Google Sheet",
    response_class=Response,
)
def pedidos_csv(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    desde: Annotated[date | None, Query(description="Primer día, hora de Lima.")] = None,
    hasta: Annotated[date | None, Query(description="Último día, incluido.")] = None,
):
    """Una fila por producto y una por el envío de cada pedido, en todos los
    estados. Se sube al Sheet en "Importar pedidos" reemplazando la hoja."""
    if desde and hasta and hasta < desde:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "La fecha final es anterior a la inicial."
        )
    pedidos = exportar.pedidos_a_exportar(sesion, desde=desde, hasta=hasta)
    hoy = datetime.now(exportar.LIMA).strftime("%Y-%m-%d")
    return Response(
        content=exportar.csv_pedidos(pedidos),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="pedidos-{hoy}.csv"'},
    )
