"""Carga de las ventas anteriores a la web: sin tocar stock e idempotente."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app import exportar, ventas_antiguas
from app.models import EstadoPedido, Pedido
from tests.test_estados_pedido import producto  # noqa: F401 (fixture)

PLANILLA_VIEJA = """N° pedido,Fecha,Estado,Cliente,Código,Producto,Cantidad,Precio unitario (S/),Total (S/)
V-001,01/10/2026,Completado,Katherine,ECN-001,Miel,2,S/ 25.00,S/ 50.00
V-001,01/10/2026,Completado,Katherine,ECN-001,Miel,1,S/ 30.00,S/ 30.00
,,,,,,,,
V-09,08/10/2026,Completado,Monchi,ECN-001,Miel,1,S/ 30.00,S/ 30.00
"""


def _archivo(tmp_path, texto):
    ruta = tmp_path / "ventas.csv"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_carga_sin_tocar_el_stock(sesion, producto, tmp_path):
    ventas = ventas_antiguas.leer(_archivo(tmp_path, PLANILLA_VIEJA))

    r = ventas_antiguas.cargar(sesion, ventas, fecha_por_defecto=None)
    sesion.commit()

    assert r["creados"] == ["V-001", "V-009"]  # V-09 se normaliza
    sesion.refresh(producto)
    assert producto.stock == 10
    v1 = sesion.scalar(select(Pedido).where(Pedido.correlativo == 1))
    assert v1.codigo_venta == "V-001"
    assert v1.numero_pedido.startswith("ECN-M-261001-")  # no adivinable
    assert v1.estado == EstadoPedido.completado
    assert v1.origen == "manual"
    assert v1.telefono_contacto is None
    assert v1.total == Decimal("80.00")
    assert [i.precio_unitario for i in v1.items] == [Decimal("25.00"), Decimal("30.00")]


def test_el_siguiente_pedido_de_la_web_sigue_la_numeracion(sesion, producto, tmp_path):
    ventas_antiguas.cargar(
        sesion, ventas_antiguas.leer(_archivo(tmp_path, PLANILLA_VIEJA)), fecha_por_defecto=None
    )
    sesion.commit()

    nuevo = Pedido(
        numero_pedido="ECN-261010-1234", nombre_contacto="Ana", telefono_contacto="987654321",
        direccion_envio="Av. 1", envio=Decimal("0"), total=Decimal("0"),
    )
    sesion.add(nuevo)
    sesion.commit()

    assert nuevo.codigo_venta == "V-010"  # después de V-009


def test_un_numero_de_venta_ocupado_por_otro_pedido_da_error(sesion, producto, tmp_path):
    ocupado = Pedido(
        numero_pedido="ECN-261010-1234", correlativo=1, nombre_contacto="Ana",
        envio=Decimal("0"), total=Decimal("0"),
    )
    sesion.add(ocupado)
    sesion.commit()

    r = ventas_antiguas.cargar(
        sesion, ventas_antiguas.leer(_archivo(tmp_path, PLANILLA_VIEJA)), fecha_por_defecto=None
    )

    assert any("V-001" in e and "ECN-261010-1234" in e for e in r["errores"])


def test_correrlo_dos_veces_no_duplica(sesion, producto, tmp_path):
    ruta = _archivo(tmp_path, PLANILLA_VIEJA)
    ventas_antiguas.cargar(sesion, ventas_antiguas.leer(ruta), fecha_por_defecto=None)
    sesion.commit()

    r = ventas_antiguas.cargar(sesion, ventas_antiguas.leer(ruta), fecha_por_defecto=None)

    assert r["creados"] == [] and r["saltados"] == ["V-001", "V-009"]
    assert sesion.scalar(select(func.count(Pedido.id))) == 2


def test_lee_el_formato_de_la_exportacion_y_usa_la_fecha_por_defecto(sesion, producto, tmp_path):
    texto = (
        ",".join(exportar.CABECERA) + "\n"
        "V-020,,,completado,Ana,ECN-001,Miel,1,30.00\n"
        "V-020,,,completado,Ana,ENVIO,Envío,1,10.00\n"
    )
    ventas = ventas_antiguas.leer(_archivo(tmp_path, texto))

    r = ventas_antiguas.cargar(sesion, ventas, fecha_por_defecto=date(2026, 9, 30))
    sesion.commit()

    assert r["creados"] == ["V-020"]
    pedido = sesion.scalar(select(Pedido).where(Pedido.correlativo == 20))
    assert pedido.envio == Decimal("10.00") and pedido.total == Decimal("40.00")
    filas = exportar.filas([pedido])
    assert filas[0][1:3] == ["2026-09-30", "2026-09-30"]


def test_codigo_inexistente_o_sin_fecha_da_error(sesion, producto, tmp_path):
    texto = PLANILLA_VIEJA + "V-010,,Completado,Fer,ECN-999,X,1,S/ 1.00,S/ 1.00\n"
    ventas = ventas_antiguas.leer(_archivo(tmp_path, texto))

    r = ventas_antiguas.cargar(sesion, ventas, fecha_por_defecto=None)

    assert any("V-010" in e for e in r["errores"])
