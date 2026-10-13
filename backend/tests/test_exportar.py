"""Exportación de pedidos para el Google Sheet: el formato es fijo."""

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import exportar
from app.models import EstadoPedido as E
from app.models import Pedido, PedidoItem, Producto
from tests.test_api_pedidos import cliente  # noqa: F401 (fixture)
from tests.test_estados_pedido import producto  # noqa: F401 (fixture)

LIMA = timezone(timedelta(hours=-5))
CABECERA = (
    "N° pedido,Fecha pedido,Fecha pago,Estado,Cliente,Código,Producto,Cantidad,"
    "Precio unitario,Código de pedido"
)


@pytest.fixture()
def otro(sesion, producto):
    p = Producto(
        codigo="ECN-002",
        nombre="Aceite, de coco",  # con coma: debe ir entre comillas
        slug="aceite",
        marca_id=producto.marca_id,
        subcategoria_id=producto.subcategoria_id,
        precio=Decimal("32.00"),
        stock=5,
    )
    sesion.add(p)
    sesion.commit()
    return p


def _pedido(
    sesion, numero, lineas, *, estado=E.pendiente, envio="10.00", creado=None, pago=None,
    origen="web",
):
    pedido = Pedido(
        numero_pedido=numero,
        origen=origen,
        nombre_contacto="Ana Torres",
        telefono_contacto="987654321",
        direccion_envio="Av. Siempre Viva 123",
        estado=estado,
        envio=Decimal(envio),
        total=Decimal("0"),
        fecha_pago=pago,
    )
    if creado:
        pedido.creado_en = creado
    for prod, cantidad, precio in lineas:
        pedido.items.append(
            PedidoItem(producto_id=prod.id, cantidad=cantidad, precio_unitario=Decimal(precio))
        )
    sesion.add(pedido)
    sesion.commit()
    return pedido


def _leer(sesion, **filtros):
    texto = exportar.csv_pedidos(exportar.pedidos_a_exportar(sesion, **filtros))
    assert texto.startswith("\ufeff")
    return list(csv.reader(io.StringIO(texto.removeprefix("\ufeff"))))


def test_la_cabecera_es_exacta(sesion):
    texto = exportar.csv_pedidos([])
    assert texto == "\ufeff" + CABECERA + "\r\n"


def test_pedido_con_dos_productos_y_envio_da_tres_filas(sesion, producto, otro):
    pedido = _pedido(sesion, "ECN-1", [(producto, 2, "30.00"), (otro, 1, "32.00")])

    _, *filas = _leer(sesion)

    assert len(filas) == 3
    assert [f[5] for f in filas] == ["ECN-001", "ECN-002", "ENVIO"]
    assert filas[2][6:] == ["Envío", "1", "10.00", "ECN-1"]
    assert {f[0] for f in filas} == {pedido.codigo_venta}
    assert {f[9] for f in filas} == {"ECN-1"}


def test_n_pedido_es_el_correlativo_y_al_final_va_el_codigo_del_cliente(sesion, producto):
    web = _pedido(sesion, "ECN-260911-3734", [(producto, 1, "30.00")])
    manual = _pedido(sesion, "ECN-M-261009-1111", [(producto, 1, "30.00")], origen="manual")

    _, *filas = _leer(sesion)

    assert web.codigo_venta.startswith("V-")
    por_venta = {f[0]: f[9] for f in filas}
    assert por_venta[web.codigo_venta] == "ECN-260911-3734"
    assert por_venta[manual.codigo_venta] == "ECN-M-261009-1111"


def test_envio_gratis_tambien_aparece_en_cero(sesion, producto):
    _pedido(sesion, "ECN-1", [(producto, 1, "30.00")], envio="0")

    _, *filas = _leer(sesion)

    assert filas[-1][5:9] == ["ENVIO", "Envío", "1", "0.00"]


def test_estados_en_minusculas_y_los_cancelados_tambien_salen(sesion, producto):
    _pedido(sesion, "ECN-1", [(producto, 1, "30.00")], estado=E.cancelado)
    _pedido(sesion, "ECN-2", [(producto, 1, "30.00")], estado=E.completado)

    _, *filas = _leer(sesion)

    assert {f[3] for f in filas} == {"cancelado", "completado"}


def test_precio_cobrado_y_no_el_actual(sesion, producto):
    _pedido(sesion, "ECN-1", [(producto, 1, "25.5")])
    producto.precio = Decimal("99.00")
    sesion.commit()

    _, primera, _ = _leer(sesion)

    assert primera[8] == "25.50"


def test_solo_el_nombre_del_cliente(sesion, producto):
    _pedido(sesion, "ECN-1", [(producto, 1, "30.00")])

    _, *filas = _leer(sesion)

    texto = ",".join(sum(filas, []))
    assert "Ana Torres" in texto
    assert "987654321" not in texto and "Siempre Viva" not in texto


def test_texto_con_coma_va_entre_comillas(sesion, otro):
    _pedido(sesion, "ECN-1", [(otro, 1, "32.00")])

    texto = exportar.csv_pedidos(exportar.pedidos_a_exportar(sesion))

    assert '"Aceite, de coco"' in texto


def test_fechas_en_hora_de_lima_y_pago_vacio_si_no_hay(sesion, producto):
    # 23:30 en Lima del 1 de octubre ya es 2 de octubre en UTC.
    tarde = datetime(2026, 10, 1, 23, 30, tzinfo=LIMA)
    _pedido(sesion, "ECN-1", [(producto, 1, "30.00")], creado=tarde)
    _pedido(sesion, "ECN-2", [(producto, 1, "30.00")], estado=E.pagado, creado=tarde, pago=tarde)

    _, *filas = _leer(sesion)

    sin_pago = next(f for f in filas if f[9] == "ECN-1")
    pagado = next(f for f in filas if f[9] == "ECN-2")
    assert sin_pago[1:3] == ["2026-10-01", ""]
    assert pagado[1:3] == ["2026-10-01", "2026-10-01"]


def test_orden_por_fecha_y_correlativo_y_filtro_por_dias(sesion, producto):
    b = _pedido(sesion, "B", [(producto, 1, "1")], creado=datetime(2026, 10, 2, 9, tzinfo=LIMA))
    a = _pedido(sesion, "A", [(producto, 1, "1")], creado=datetime(2026, 10, 2, 9, tzinfo=LIMA))
    z = _pedido(sesion, "Z", [(producto, 1, "1")], creado=datetime(2026, 10, 1, 9, tzinfo=LIMA))

    _, *filas = _leer(sesion)
    assert [f[9] for f in filas[::2]] == ["Z", "B", "A"]  # misma hora: va el correlativo
    assert b.correlativo < a.correlativo

    _, *filas = _leer(sesion, desde=datetime(2026, 10, 2).date())
    assert {f[0] for f in filas} == {a.codigo_venta, b.codigo_venta}
    assert z.codigo_venta not in {f[0] for f in filas}


def test_endpoint_descarga_con_nombre_de_archivo(cliente, sesion, producto):
    _pedido(sesion, "ECN-1", [(producto, 1, "30.00")])

    r = cliente.get("/api/v1/admin/export/pedidos.csv")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="pedidos-' in r.headers["content-disposition"]
    assert r.text.removeprefix("\ufeff").startswith(CABECERA)
