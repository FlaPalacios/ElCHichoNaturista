"""Ventas e ingresos entre fechas, para los gráficos del panel.

Un pedido cuenta como venta desde que el pago está confirmado (la misma regla
del resumen). Las fechas se leen en hora de Lima: un pedido de las 9 p. m. del
día 30 no debe caer en el día 1 por culpa del UTC.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.resumen import ESTADOS_VENDIDOS
from app.database import obtener_sesion
from app.models import (
    Admin,
    Categoria,
    EstadoPedido,
    Marca,
    Pedido,
    PedidoItem,
    Producto,
    Subcategoria,
)
from app.seguridad import admin_actual

router = APIRouter(prefix="/ventas", tags=["admin"])

LIMA = timezone(timedelta(hours=-5))  # sin horario de verano
MAX_DIAS = 731
# "activos": además de los pagados, los nuevos que aún no confirman pago.
ESTADOS_ACTIVOS = (EstadoPedido.pendiente, *ESTADOS_VENDIDOS)
ESTADOS = {"pagados": ESTADOS_VENDIDOS, "activos": ESTADOS_ACTIVOS}

Agrupar = Literal["auto", "dia", "semana", "mes"]


def _dinero(valor) -> float:
    return round(float(valor or 0), 2)


def _limites(desde: date, hasta: date) -> tuple[datetime, datetime]:
    """Medianoche de Lima del primer día, y de la medianoche siguiente al último."""
    return (
        datetime(desde.year, desde.month, desde.day, tzinfo=LIMA),
        datetime(hasta.year, hasta.month, hasta.day, tzinfo=LIMA) + timedelta(days=1),
    )


def _validar_rango(desde: date, hasta: date) -> int:
    if hasta < desde:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "La fecha final es anterior a la inicial."
        )
    dias = (hasta - desde).days + 1
    if dias > MAX_DIAS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "El rango máximo es de dos años."
        )
    return dias


def _agrupacion(agrupar: str, dias: int) -> str:
    if agrupar != "auto":
        return agrupar
    return "dia" if dias <= 45 else "semana" if dias <= 200 else "mes"


def _inicio_periodo(dia: date, agrupar: str) -> date:
    if agrupar == "semana":
        return dia - timedelta(days=dia.weekday())  # lunes
    if agrupar == "mes":
        return dia.replace(day=1)
    return dia


def _siguiente(dia: date, agrupar: str) -> date:
    if agrupar == "semana":
        return dia + timedelta(days=7)
    if agrupar == "mes":
        return (dia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return dia + timedelta(days=1)


def _periodos(desde: date, hasta: date, agrupar: str) -> list[date]:
    actual, salida = _inicio_periodo(desde, agrupar), []
    while actual <= hasta:
        salida.append(actual)
        actual = _siguiente(actual, agrupar)
    return salida


def _donde(estados, ini: datetime, fin: datetime):
    return (Pedido.estado.in_(estados), Pedido.creado_en >= ini, Pedido.creado_en < fin)


def _cifras(sesion: Session, estados, ini: datetime, fin: datetime) -> dict:
    pedidos, ventas, envio, productos = sesion.execute(
        select(
            func.count(Pedido.id),
            func.coalesce(func.sum(Pedido.total), 0),
            func.coalesce(func.sum(Pedido.envio), 0),
            func.coalesce(func.sum(Pedido.total - Pedido.envio), 0),
        ).where(*_donde(estados, ini, fin))
    ).one()
    unidades = sesion.scalar(
        select(func.coalesce(func.sum(PedidoItem.cantidad), 0))
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .where(*_donde(estados, ini, fin))
    )
    return {
        "ventas": _dinero(ventas),
        "pedidos": pedidos,
        "ticket": _dinero(Decimal(ventas) / pedidos) if pedidos else 0.0,
        "unidades": int(unidades),
        "envio": _dinero(envio),
        "productos": _dinero(productos),
    }


def _serie(
    sesion: Session, estados, desde: date, hasta: date, agrupar: str
) -> list[dict]:
    ini, fin = _limites(desde, hasta)
    cubeta = cast(
        func.date_trunc(
            {"dia": "day", "semana": "week", "mes": "month"}[agrupar],
            func.timezone("America/Lima", Pedido.creado_en),
        ),
        Date,
    )
    filas = {
        dia: (pedidos, ventas)
        for dia, pedidos, ventas in sesion.execute(
            select(cubeta, func.count(Pedido.id), func.sum(Pedido.total))
            .where(*_donde(estados, ini, fin))
            .group_by(cubeta)
        )
    }
    return [
        {
            "periodo": p.isoformat(),
            "pedidos": filas.get(p, (0, 0))[0],
            "ventas": _dinero(filas.get(p, (0, 0))[1]),
        }
        for p in _periodos(desde, hasta, agrupar)
    ]


def _por_producto(sesion: Session, estados, ini: datetime, fin: datetime, columna, limite: int):
    """Importe de productos (precio × cantidad) agrupado por `columna`."""
    importe = func.sum(PedidoItem.cantidad * PedidoItem.precio_unitario)
    return [
        {"nombre": nombre, "unidades": int(unidades), "importe": _dinero(total)}
        for nombre, unidades, total in sesion.execute(
            select(columna, func.sum(PedidoItem.cantidad), importe)
            .select_from(PedidoItem)
            .join(Pedido, Pedido.id == PedidoItem.pedido_id)
            .join(Producto, Producto.id == PedidoItem.producto_id)
            .join(Subcategoria, Subcategoria.id == Producto.subcategoria_id)
            .join(Categoria, Categoria.id == Subcategoria.categoria_id)
            .join(Marca, Marca.id == Producto.marca_id)
            .where(*_donde(estados, ini, fin))
            .group_by(columna)
            .order_by(importe.desc())
            .limit(limite)
        )
    ]


@router.get("", summary="Ventas e ingresos entre dos fechas")
def ventas(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    desde: Annotated[date | None, Query(description="Primer día (hora de Lima).")] = None,
    hasta: Annotated[date | None, Query(description="Último día, incluido.")] = None,
    agrupar: Annotated[Agrupar, Query()] = "auto",
    estado: Annotated[
        Literal["pagados", "activos"],
        Query(description="pagados: pago confirmado en adelante; activos: suma los nuevos."),
    ] = "pagados",
    comparar: Annotated[bool, Query(description="Incluye el periodo anterior.")] = True,
):
    hoy = datetime.now(LIMA).date()
    hasta = hasta or hoy
    desde = desde or hasta - timedelta(days=29)
    dias = _validar_rango(desde, hasta)
    unidad = _agrupacion(agrupar, dias)
    estados = ESTADOS[estado]
    ini, fin = _limites(desde, hasta)

    respuesta = {
        "rango": {
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "dias": dias,
            "agrupar": unidad,
            "estado": estado,
        },
        "cifras": _cifras(sesion, estados, ini, fin),
        "serie": _serie(sesion, estados, desde, hasta, unidad),
        "previo": None,
        "top_productos": [
            {"codigo": c, "nombre": n, "unidades": int(u), "importe": _dinero(i)}
            for c, n, u, i in sesion.execute(
                select(
                    Producto.codigo,
                    Producto.nombre,
                    func.sum(PedidoItem.cantidad),
                    func.sum(PedidoItem.cantidad * PedidoItem.precio_unitario).label("i"),
                )
                .join(PedidoItem, PedidoItem.producto_id == Producto.id)
                .join(Pedido, Pedido.id == PedidoItem.pedido_id)
                .where(*_donde(estados, ini, fin))
                .group_by(Producto.codigo, Producto.nombre)
                .order_by(func.sum(PedidoItem.cantidad * PedidoItem.precio_unitario).desc())
                .limit(10)
            )
        ],
        "por_categoria": _por_producto(sesion, estados, ini, fin, Categoria.nombre, 8),
        "por_marca": _por_producto(sesion, estados, ini, fin, Marca.nombre, 8),
        "por_departamento": [
            {"nombre": d or "Sin dato", "pedidos": p, "importe": _dinero(t)}
            for d, p, t in sesion.execute(
                select(Pedido.departamento, func.count(Pedido.id), func.sum(Pedido.total))
                .where(*_donde(estados, ini, fin))
                .group_by(Pedido.departamento)
                .order_by(func.sum(Pedido.total).desc())
                .limit(10)
            )
        ],
        # Todos los estados, sin importar el filtro: sirve para ver cuántos
        # pedidos se quedan sin pagar o se cancelan.
        "estados": [
            {"estado": e.value, "pedidos": n}
            for e, n in sesion.execute(
                select(Pedido.estado, func.count(Pedido.id))
                .where(Pedido.creado_en >= ini, Pedido.creado_en < fin)
                .group_by(Pedido.estado)
            )
        ],
    }

    if comparar:
        # El periodo de igual duración justo antes.
        p_hasta = desde - timedelta(days=1)
        p_desde = p_hasta - timedelta(days=dias - 1)
        p_ini, p_fin = _limites(p_desde, p_hasta)
        respuesta["previo"] = {
            "desde": p_desde.isoformat(),
            "hasta": p_hasta.isoformat(),
            "cifras": _cifras(sesion, estados, p_ini, p_fin),
            "serie": _serie(sesion, estados, p_desde, p_hasta, unidad),
        }
    return respuesta


@router.get(
    "/exportar",
    summary="Descarga los pedidos del rango como CSV",
    response_class=Response,
)
def exportar(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    admin: Annotated[Admin, Depends(admin_actual)],
    desde: Annotated[date, Query()],
    hasta: Annotated[date, Query()],
    estado: Annotated[Literal["pagados", "activos"], Query()] = "pagados",
):
    _validar_rango(desde, hasta)
    ini, fin = _limites(desde, hasta)
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter="\t", lineterminator="\n")
    escritor.writerow(
        [
            "pedido", "fecha", "estado", "cliente", "telefono", "departamento",
            "provincia", "distrito", "subtotal", "envio", "total",
        ]
    )
    for p in sesion.scalars(
        select(Pedido)
        .where(*_donde(ESTADOS[estado], ini, fin))
        .order_by(Pedido.creado_en)
    ):
        escritor.writerow(
            [
                p.numero_pedido,
                p.creado_en.astimezone(LIMA).strftime("%Y-%m-%d %H:%M"),
                p.estado.value,
                p.nombre_contacto,
                p.telefono_contacto,
                p.departamento or "",
                p.provincia or "",
                p.distrito or "",
                f"{p.subtotal:.2f}",
                f"{p.envio:.2f}",
                f"{p.total:.2f}",
            ]
        )
    return Response(
        content="﻿" + salida.getvalue(),
        media_type="text/tab-separated-values; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ventas_{desde}_{hasta}.tsv"'
        },
    )
