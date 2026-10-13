"""Los endpoints del panel para el estado y la fecha de pago."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import obtener_sesion
from app.main import app
from app.models import EstadoPedido as E
from app.seguridad import admin_actual
from tests.test_estados_pedido import _pedido, producto  # noqa: F401 (fixture)

LIMA = timezone(timedelta(hours=-5))


@pytest.fixture()
def cliente(sesion):
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    app.dependency_overrides[admin_actual] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_marcar_pagado_sin_stock_responde_422_con_el_motivo(cliente, sesion, producto):
    pedido = _pedido(sesion, producto, cantidad=11)

    r = cliente.patch(f"/api/v1/admin/pedidos/{pedido.numero_pedido}/estado", json={"estado": "pagado"})

    assert r.status_code == 422
    assert "quedan 10" in r.json()["detail"]


def test_marcar_pagado_devuelve_la_fecha_de_pago(cliente, sesion, producto):
    pedido = _pedido(sesion, producto)

    r = cliente.patch(f"/api/v1/admin/pedidos/{pedido.numero_pedido}/estado", json={"estado": "pagado"})

    assert r.status_code == 200
    assert r.json()["estado"] == "pagado"
    assert r.json()["fecha_pago"] is not None


def test_fecha_de_pago_sin_zona_se_entiende_como_hora_de_lima(cliente, sesion, producto):
    pedido = _pedido(sesion, producto, estado=E.pagado)

    r = cliente.patch(
        f"/api/v1/admin/pedidos/{pedido.numero_pedido}/fecha-pago",
        json={"fecha_pago": "2026-10-01T21:30"},
    )

    assert r.status_code == 200
    guardada = datetime.fromisoformat(r.json()["fecha_pago"])
    assert guardada == datetime(2026, 10, 1, 21, 30, tzinfo=LIMA)


def test_fecha_de_pago_en_un_pendiente_responde_422(cliente, sesion, producto):
    pedido = _pedido(sesion, producto)

    r = cliente.patch(
        f"/api/v1/admin/pedidos/{pedido.numero_pedido}/fecha-pago",
        json={"fecha_pago": "2026-10-01T10:00"},
    )

    assert r.status_code == 422
