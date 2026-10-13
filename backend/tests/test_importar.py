"""Importación de catálogo por TSV: se empareja por código y no pisa el stock."""

from sqlalchemy import select

from app import crud, importar
from app.models import Producto
from app.schemas import ProductoCrear

CABECERA = "\t".join(importar.COLUMNAS)


def _fila(codigo, nombre="Miel", precio="10.00", stock="5", slug=None):
    valores = dict.fromkeys(importar.COLUMNAS, "")
    valores.update(
        codigo=codigo,
        nombre=nombre,
        slug=slug or nombre.lower().replace(" ", "-"),
        marca_slug="marca-uno",
        subcategoria_slug="mieles",
        precio=precio,
        stock=stock,
    )
    return "\t".join(valores[c] for c in importar.COLUMNAS)


def _importar(sesion, *filas, aplicar=True):
    texto = "\n".join([CABECERA, *filas]).encode("utf-8")
    leidas, _ = importar.leer_planilla(texto)
    return importar.procesar(sesion, leidas, aplicar=aplicar)


def _stock(sesion, codigo):
    sesion.expire_all()
    return sesion.scalar(select(Producto.stock).where(Producto.codigo == codigo))


def test_crea_producto_nuevo_con_el_stock_de_la_planilla(sesion, catalogo_base):
    r = _importar(sesion, _fila("ECN-001", stock="7"))

    assert (r["creados"], r["actualizados"], r["filas_con_error"]) == (1, 0, 0)
    assert _stock(sesion, "ECN-001") == 7


def test_actualiza_sin_tocar_el_stock(sesion, catalogo_base):
    _importar(sesion, _fila("ECN-001", precio="10.00", stock="7"))

    r = _importar(sesion, _fila("ECN-001", nombre="Miel Pura", precio="12.50", stock="99"))

    assert (r["creados"], r["actualizados"]) == (0, 1)
    producto = crud.obtener_producto_admin(sesion, "ECN-001")
    assert producto.nombre == "Miel Pura"
    assert float(producto.precio) == 12.50
    assert producto.stock == 7


def test_stock_vacio_en_un_producto_existente_no_lo_deja_en_cero(sesion, catalogo_base):
    _importar(sesion, _fila("ECN-001", stock="7"))

    r = _importar(sesion, _fila("ECN-001", stock=""))

    assert r["filas_con_error"] == 0
    assert _stock(sesion, "ECN-001") == 7


def test_codigo_repetido_en_el_archivo_se_rechaza(sesion, catalogo_base):
    r = _importar(
        sesion,
        _fila("ECN-001", nombre="Miel"),
        _fila("ECN-001", nombre="Otra miel"),
    )

    assert r["filas_con_error"] == 1
    assert "ya aparece" in r["errores"][0]
    assert r["aplicado"] is False
    assert sesion.scalar(select(Producto.id)) is None  # no se guardó nada


def test_el_panel_rechaza_un_codigo_que_ya_existe(sesion, catalogo_base):
    _importar(sesion, _fila("ECN-001"))
    existente = crud.obtener_producto_admin(sesion, "ECN-001")
    datos = ProductoCrear(
        codigo="ECN-001",
        nombre="Otro",
        slug="otro",
        marca_id=existente.marca_id,
        subcategoria_id=existente.subcategoria_id,
        precio=5,
        stock=1,
    ).model_dump()

    try:
        crud.guardar_producto(sesion, datos)
    except crud.ValorRepetido as error:
        assert "codigo" in str(error)
    else:
        raise AssertionError("debió rechazar el código duplicado")


def test_el_resumen_cuenta_creados_actualizados_y_errores(sesion, catalogo_base):
    _importar(sesion, _fila("ECN-001"))

    r = _importar(
        sesion,
        _fila("ECN-001", precio="11.00"),
        _fila("ECN-002", nombre="Miel B"),
        _fila("ECN-003", nombre="Miel C", precio="abc"),
        aplicar=False,
    )

    assert (r["creados"], r["actualizados"], r["filas_con_error"]) == (1, 1, 1)
