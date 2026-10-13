"""Registrar desde el panel una venta cerrada fuera de la web."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import crud
from app.models import EstadoPedido as E
from tests.test_api_pedidos import cliente  # noqa: F401 (fixture)
from tests.test_estados_pedido import producto  # noqa: F401 (fixture)

LIMA = timezone(timedelta(hours=-5))


def _venta(sesion, producto, *, cantidad=2, precio=None, pagado=True, fecha=None, envio="0"):
    pedido = crud.crear_venta_manual(
        sesion,
        nombre_contacto="Carolina",
        telefono_contacto=None,
        fecha=fecha,
        items=[(producto.id, cantidad, precio)],
        envio=Decimal(envio),
        pagado=pagado,
        nota_interna=None,
    )
    sesion.commit()
    sesion.refresh(producto)
    return pedido


def test_pagada_descuenta_stock_y_anota_la_fecha(sesion, producto):
    pedido = _venta(sesion, producto)

    assert pedido.estado == E.pagado
    assert pedido.fecha_pago is not None
    assert producto.stock == 8
    assert pedido.origen == "manual"
    assert pedido.numero_pedido.startswith("ECN-M-")
    assert pedido.codigo_venta.startswith("V-")


def test_pendiente_no_toca_el_stock_hasta_marcarla_pagada(sesion, producto):
    pedido = _venta(sesion, producto, pagado=False)
    assert pedido.estado == E.pendiente and producto.stock == 10

    crud.cambiar_estado(sesion, pedido, E.pagado)
    sesion.commit()
    sesion.refresh(producto)

    assert producto.stock == 8


def test_precio_distinto_al_de_lista_y_envio_suman_al_total(sesion, producto):
    pedido = _venta(sesion, producto, cantidad=2, precio=Decimal("25.00"), envio="10")

    assert pedido.items[0].precio_unitario == Decimal("25.00")
    assert pedido.total == Decimal("60.00")


def test_sin_precio_usa_el_de_lista(sesion, producto):
    pedido = _venta(sesion, producto, cantidad=1)

    assert pedido.items[0].precio_unitario == Decimal("30.00")


def test_acepta_productos_inactivos(sesion, producto):
    producto.activo = False
    sesion.commit()

    pedido = _venta(sesion, producto, cantidad=1)

    assert pedido.items[0].producto_id == producto.id


def test_venta_de_otro_dia_queda_con_esa_fecha_de_pedido_y_de_pago(sesion, producto):
    pedido = _venta(sesion, producto, fecha=date(2026, 10, 5))

    assert pedido.creado_en.astimezone(LIMA).date() == date(2026, 10, 5)
    assert pedido.fecha_pago.astimezone(LIMA).date() == date(2026, 10, 5)
    assert pedido.numero_pedido.startswith("ECN-M-261005-")


def test_sin_stock_no_se_registra(sesion, producto):
    with pytest.raises(crud.StockInsuficiente):
        _venta(sesion, producto, cantidad=11)


def test_fecha_futura_no_se_acepta(sesion, producto):
    with pytest.raises(crud.ErrorPedido, match="futura"):
        _venta(sesion, producto, fecha=datetime.now(LIMA).date() + timedelta(days=1))


def test_endpoint_crea_la_venta_y_responde_201(cliente, sesion, producto):
    r = cliente.post(
        "/api/v1/admin/pedidos/manual",
        json={
            "nombre_contacto": "Carolina",
            "telefono_contacto": "  ",
            "items": [{"producto_id": producto.id, "cantidad": 3}],
        },
    )

    assert r.status_code == 201
    datos = r.json()
    assert datos["estado"] == "pagado"
    assert datos["origen"] == "manual"
    assert datos["telefono_contacto"] is None
    assert datos["codigo_venta"].startswith("V-")
    sesion.refresh(producto)
    assert producto.stock == 7


def test_endpoint_sin_stock_responde_422(cliente, sesion, producto):
    r = cliente.post(
        "/api/v1/admin/pedidos/manual",
        json={"nombre_contacto": "Carolina", "items": [{"producto_id": producto.id, "cantidad": 50}]},
    )

    assert r.status_code == 422
    assert "quedan 10" in r.json()["detail"]
