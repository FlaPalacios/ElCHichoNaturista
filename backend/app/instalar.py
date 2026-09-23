"""Deja la base lista de una sola vez.

    python -m app.instalar            # crea lo que falte, no borra nada
    python -m app.instalar --reset    # borra TODO y vuelve a empezar

Hace, en este orden, lo que si no habría que recordar comando por comando:

    1. las migraciones (alembic upgrade head)
    2. el ubigeo del Perú y las tarifas de envío
    3. el catálogo desde las planillas de `app/datos`
    4. el usuario del panel, con la clave del `.env`

Sin `--reset` es seguro correrlo las veces que quieras: solo agrega lo que
falta y no toca lo que ya editaste desde el panel. Con `--reset` se borra el
catálogo, los pedidos y los ajustes, que es justo lo que hace falta al pasar de
las pruebas a los datos de verdad.
"""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select

from app import crear_admin, seed, ubigeo
from app.config import ajustes
from app.database import SesionLocal
from app.models import (
    Categoria,
    Configuracion,
    ImagenProducto,
    Marca,
    Pedido,
    PedidoItem,
    Producto,
    Subcategoria,
    TarifaEnvio,
)

RAIZ = Path(__file__).resolve().parent.parent


def migrar() -> None:
    print("\n· Migraciones")
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ / "alembic"))
    command.upgrade(configuracion, "head")


def vaciar(sesion) -> None:
    """Borra los datos del negocio. El ubigeo no se toca: no es dato de nadie."""
    cuantos = {
        "pedidos": sesion.scalar(select(func.count()).select_from(Pedido)),
        "productos": sesion.scalar(select(func.count()).select_from(Producto)),
        "ajustes": sesion.scalar(select(func.count()).select_from(Configuracion)),
    }
    print(
        f"  se van a borrar: {cuantos['pedidos']} pedidos, "
        f"{cuantos['productos']} productos y {cuantos['ajustes']} ajustes editados"
    )
    # El ubigeo se queda (es el padrón del INEI, no datos del negocio), pero
    # las tarifas sí vuelven a su valor de fábrica: se recrean enseguida.
    for tabla in (
        PedidoItem,
        Pedido,
        ImagenProducto,
        Producto,
        Subcategoria,
        Categoria,
        Marca,
        Configuracion,
        TarifaEnvio,
    ):
        sesion.execute(delete(tabla))
    sesion.commit()
    print("  base vaciada")


def main() -> None:
    analizador = argparse.ArgumentParser(description="Prepara la base de datos.")
    analizador.add_argument(
        "--reset",
        action="store_true",
        help="borra pedidos, catálogo y ajustes antes de cargar",
    )
    analizador.add_argument(
        "--si",
        action="store_true",
        help="no preguntar antes de borrar (para scripts)",
    )
    argumentos = analizador.parse_args()

    print(f"Base de datos: {ajustes.database_url.rsplit('@', 1)[-1]}")

    migrar()

    if argumentos.reset:
        print("\n· Borrado")
        with SesionLocal() as sesion:
            if not argumentos.si:
                print("  Esto NO se puede deshacer.")
                if input("  Escribe 'borrar' para continuar: ").strip().lower() != "borrar":
                    raise SystemExit("  Cancelado: no se borró nada.")
            vaciar(sesion)

    print("\n· Ubigeo y tarifas de envío")
    with SesionLocal() as sesion:
        ubigeo.cargar_ubigeo(sesion)
        ubigeo.cargar_tarifas(sesion)
        sesion.commit()

    print("\n· Catálogo")
    with SesionLocal() as sesion:
        marcas = seed.sembrar_marcas(sesion)
        categorias = seed.sembrar_categorias(sesion)
        subcategorias = seed.sembrar_subcategorias(sesion, categorias)
        seed.sembrar_productos(sesion, marcas, subcategorias)
        seed.sembrar_imagenes(sesion)
        sesion.commit()

    print("\n· Usuario del panel")
    crear_admin.main()

    with SesionLocal() as sesion:
        activos = sesion.scalar(
            select(func.count()).select_from(Producto).where(Producto.activo.is_(True))
        )
    print(f"\nListo: {activos} productos a la venta.")
    print("Levanta la API con: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
