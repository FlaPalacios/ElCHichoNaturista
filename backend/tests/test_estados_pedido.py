"""Cada cambio de estado del pedido y lo que le hace al stock y a la fecha de pago."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app import crud
from app.models import EstadoPedido as E
from app.models import Marca, Pedido, PedidoItem, Producto, Subcategoria


@pytest.fixture()
def producto(sesion, catalogo_base):
    p = Producto(
        codigo="ECN-001",
        nombre="Miel",
        slug="miel",
        marca_id=sesion.query(Marca.id).scalar(),
        subcategoria_id=sesion.query(Subcategoria.id).scalar(),
        precio=Decimal("30.00"),
        stock=10,
    )
    sesion.add(p)
    sesion.commit()
    return p


def _pedido(sesion, producto, cantidad=3, estado=E.pendiente):
    pedido = Pedido(
        numero_pedido=f"T-{estado.value}-{cantidad}",
        nombre_contacto="Ana",
        telefono_contacto="987654321",
        direccion_envio="Av. Siempre Viva 123",
        estado=estado,
        envio=Decimal("10.00"),
        total=Decimal("100.00"),
    )
    pedido.items.append(
        PedidoItem(producto_id=producto.id, cantidad=cantidad, precio_unitario=producto.precio)
    )
    sesion.add(pedido)
    sesion.commit()
    return pedido


def _stock(sesion, producto):
    sesion.refresh(producto)
    return producto.stock


def _ir(sesion, pedido, *estados):
    for estado in estados:
        crud.cambiar_estado(sesion, pedido, estado)
        sesion.commit()


def test_pendiente_a_pagado_descuenta_y_anota_la_fecha(sesion, producto):
    pedido = _pedido(sesion, producto)

    _ir(sesion, pedido, E.pagado)

    assert _stock(sesion, producto) == 7
    assert pedido.fecha_pago is not None


def test_pagado_enviado_completado_no_vuelve_a_descontar(sesion, producto):
    pedido = _pedido(sesion, producto)

    _ir(sesion, pedido, E.pagado, E.enviado, E.completado)

    assert _stock(sesion, producto) == 7


@pytest.mark.parametrize("desde", [E.pagado, E.enviado, E.completado])
def test_cancelar_un_pedido_pagado_devuelve_el_stock(sesion, producto, desde):
    pedido = _pedido(sesion, producto)
    _ir(sesion, pedido, E.pagado, desde)

    _ir(sesion, pedido, E.cancelado)

    assert _stock(sesion, producto) == 10
    assert pedido.fecha_pago is not None  # el pago existió, aunque luego se cancele


def test_cancelar_un_pedido_pendiente_no_toca_el_stock(sesion, producto):
    pedido = _pedido(sesion, producto)

    _ir(sesion, pedido, E.cancelado)

    assert _stock(sesion, producto) == 10
    assert pedido.fecha_pago is None


def test_sin_stock_no_deja_marcar_pagado_y_no_cambia_nada(sesion, producto):
    pedido = _pedido(sesion, producto, cantidad=11)

    with pytest.raises(crud.StockInsuficiente, match="quedan 10, se pidieron 11"):
        crud.cambiar_estado(sesion, pedido, E.pagado)
    sesion.rollback()

    assert _stock(sesion, producto) == 10
    sesion.refresh(pedido)
    assert pedido.estado == E.pendiente
    assert pedido.fecha_pago is None


def test_lineas_repetidas_del_mismo_producto_se_suman_al_validar(sesion, producto):
    pedido = _pedido(sesion, producto, cantidad=6)
    pedido.items.append(
        PedidoItem(producto_id=producto.id, cantidad=6, precio_unitario=producto.precio)
    )
    sesion.commit()

    with pytest.raises(crud.StockInsuficiente):
        crud.cambiar_estado(sesion, pedido, E.pagado)
    sesion.rollback()
    assert _stock(sesion, producto) == 10


def test_repetir_el_mismo_estado_no_hace_nada(sesion, producto):
    pedido = _pedido(sesion, producto)
    _ir(sesion, pedido, E.pagado, E.pagado)

    assert _stock(sesion, producto) == 7


def test_volver_a_pendiente_devuelve_stock_y_borra_la_fecha(sesion, producto):
    pedido = _pedido(sesion, producto)
    _ir(sesion, pedido, E.pagado, E.pendiente)

    assert _stock(sesion, producto) == 10
    assert pedido.fecha_pago is None


def test_reactivar_un_cancelado_vuelve_a_descontar_y_conserva_la_fecha(sesion, producto):
    pedido = _pedido(sesion, producto)
    _ir(sesion, pedido, E.pagado)
    fecha = pedido.fecha_pago
    _ir(sesion, pedido, E.cancelado, E.pagado)

    assert _stock(sesion, producto) == 7
    assert pedido.fecha_pago == fecha


def test_la_fecha_de_pago_se_corrige_a_mano(sesion, producto):
    pedido = _pedido(sesion, producto)
    _ir(sesion, pedido, E.pagado)
    otra = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)

    crud.cambiar_fecha_pago(sesion, pedido, otra)
    sesion.commit()

    assert pedido.fecha_pago == otra


def test_un_pendiente_no_acepta_fecha_de_pago(sesion, producto):
    pedido = _pedido(sesion, producto)

    with pytest.raises(crud.ErrorPedido):
        crud.cambiar_fecha_pago(sesion, pedido, datetime.now(timezone.utc))
