"""Exportación de pedidos para el Google Sheet de costos.

El Sheet lee las columnas por posición (pestaña "Importar pedidos"), así que el
formato es fijo: no cambiar el orden ni el texto de la cabecera sin cambiar
también el Sheet.

Se exporta el historial completo, en todos los estados: el Sheet decide qué
cuenta como venta, y al reemplazar la hoja entera cada vez nada se duplica.

"N° pedido" es el número de venta correlativo (V-001…), que comparten la web y
el Sheet. "Código de pedido" es el que ve el cliente (ECN-AAMMDD-NNNN en la
web, ECN-M-AAMMDD-NNNN en las ventas manuales), para encontrarlo en el panel.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Pedido, PedidoItem

LIMA = timezone(timedelta(hours=-5))  # sin horario de verano

CABECERA = [
    "N° pedido",
    "Fecha pedido",
    "Fecha pago",
    "Estado",
    "Cliente",
    "Código",
    "Producto",
    "Cantidad",
    "Precio unitario",
    "Código de pedido",
]
CODIGO_ENVIO = "ENVIO"


def _dia(momento: datetime | None) -> str:
    return momento.astimezone(LIMA).strftime("%Y-%m-%d") if momento else ""


def pedidos_a_exportar(
    sesion: Session, *, desde: date | None = None, hasta: date | None = None
) -> list[Pedido]:
    """Todos los pedidos, del más viejo al más nuevo. `desde`/`hasta` son días
    completos en hora de Lima, ambos incluidos."""
    consulta = select(Pedido).options(
        selectinload(Pedido.items).joinedload(PedidoItem.producto)
    )
    if desde is not None:
        consulta = consulta.where(
            Pedido.creado_en >= datetime(desde.year, desde.month, desde.day, tzinfo=LIMA)
        )
    if hasta is not None:
        fin = datetime(hasta.year, hasta.month, hasta.day, tzinfo=LIMA) + timedelta(days=1)
        consulta = consulta.where(Pedido.creado_en < fin)
    consulta = consulta.order_by(Pedido.creado_en, Pedido.correlativo)
    return list(sesion.scalars(consulta).unique())


def filas(pedidos: list[Pedido]) -> list[list[str]]:
    """Una fila por producto del pedido, más una del envío."""
    salida = []
    for p in pedidos:
        comunes = [
            p.codigo_venta,
            _dia(p.creado_en),
            _dia(p.fecha_pago),
            p.estado.value,
            p.nombre_contacto,  # solo el nombre: nada de teléfono ni dirección
        ]
        # Orden estable dentro del pedido: el de las líneas al crearlo.
        for item in sorted(p.items, key=lambda i: i.id):
            salida.append(
                comunes
                + [
                    item.producto.codigo,
                    item.producto.nombre,
                    str(item.cantidad),
                    f"{item.precio_unitario:.2f}",  # el precio cobrado, no el actual
                    p.numero_pedido,
                ]
            )
        # Siempre va, aunque sea 0: así el Sheet ve que fue envío gratis.
        salida.append(comunes + [CODIGO_ENVIO, "Envío", "1", f"{p.envio:.2f}", p.numero_pedido])
    return salida


def csv_pedidos(pedidos: list[Pedido]) -> str:
    """CSV con BOM (para que Excel y Sheets respeten las tildes), separado por
    comas y con comillas solo donde hacen falta."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(CABECERA)
    escritor.writerows(filas(pedidos))
    return "﻿" + salida.getvalue()
