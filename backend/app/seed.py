"""Puebla la base con el catálogo de ejemplo.

    python -m app.seed            # crea o actualiza (idempotente)
    python -m app.seed --reset    # borra el catálogo y lo vuelve a cargar

Los datos salen de `app/datos_semilla.json`, generado a partir de
`src/data/productos.js` del frontend, para que ambos lados coincidan cuando se
conecten en la etapa 4.
"""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import SesionLocal
from app.models import Categoria, PedidoItem, Producto

ARCHIVO_DATOS = Path(__file__).parent / "datos_semilla.json"


def cargar_datos() -> dict:
    with ARCHIVO_DATOS.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def sembrar_categorias(sesion: Session, categorias: list[dict]) -> dict[str, Categoria]:
    """Crea o actualiza categorías por slug. Devuelve el mapa slug -> Categoria."""
    por_slug: dict[str, Categoria] = {}
    nuevas = 0

    for datos in categorias:
        categoria = sesion.scalar(select(Categoria).where(Categoria.slug == datos["slug"]))
        if categoria is None:
            categoria = Categoria(slug=datos["slug"])
            sesion.add(categoria)
            nuevas += 1
        categoria.nombre = datos["nombre"]
        categoria.orden = datos["orden"]
        por_slug[datos["slug"]] = categoria

    sesion.flush()
    print(f"  categorías: {len(categorias)} procesadas ({nuevas} nuevas)")
    return por_slug


def sembrar_productos(
    sesion: Session, productos: list[dict], categorias: dict[str, Categoria]
) -> None:
    nuevos = 0

    for datos in productos:
        categoria = categorias.get(datos["categoria_slug"])
        if categoria is None:
            raise SystemExit(
                f"El producto '{datos['slug']}' apunta a la categoría "
                f"'{datos['categoria_slug']}', que no está en la semilla."
            )

        producto = sesion.scalar(select(Producto).where(Producto.slug == datos["slug"]))
        if producto is None:
            producto = Producto(slug=datos["slug"])
            sesion.add(producto)
            nuevos += 1

        producto.nombre = datos["nombre"]
        producto.descripcion_corta = datos["descripcion_corta"]
        producto.descripcion_larga = datos["descripcion_larga"]
        producto.modo_uso = datos["modo_uso"]
        producto.presentacion = datos["presentacion"]
        producto.origen = datos["origen"]
        producto.beneficios = datos["beneficios"]
        producto.categoria_id = categoria.id
        producto.precio = Decimal(datos["precio"])
        producto.precio_antes = (
            Decimal(datos["precio_antes"]) if datos["precio_antes"] else None
        )
        producto.imagen_url = datos["imagen_url"]
        producto.stock = datos["stock"]
        producto.activo = datos["activo"]
        producto.destacado = datos["destacado"]
        producto.mas_vendido = datos["mas_vendido"]

    sesion.flush()
    print(f"  productos:  {len(productos)} procesados ({nuevos} nuevos)")


def limpiar(sesion: Session) -> None:
    """Borra el catálogo. No toca pedidos si ya hay alguno que dependa de él."""
    if sesion.scalar(select(PedidoItem).limit(1)) is not None:
        raise SystemExit(
            "Hay pedidos con items en la base: --reset borraría productos "
            "referenciados. Limpia los pedidos primero."
        )
    sesion.execute(delete(Producto))
    sesion.execute(delete(Categoria))
    sesion.flush()
    print("  catálogo anterior borrado")


def main() -> None:
    analizador = argparse.ArgumentParser(description="Carga el catálogo de ejemplo.")
    analizador.add_argument(
        "--reset",
        action="store_true",
        help="borra categorías y productos antes de cargar",
    )
    argumentos = analizador.parse_args()

    datos = cargar_datos()
    print("Sembrando catálogo de El Chico Naturista…")

    with SesionLocal() as sesion:
        if argumentos.reset:
            limpiar(sesion)

        categorias = sembrar_categorias(sesion, datos["categorias"])
        sembrar_productos(sesion, datos["productos"], categorias)
        sesion.commit()

        activos = sesion.scalar(
            select(func.count()).select_from(Producto).where(Producto.activo.is_(True))
        )
        print(f"Listo. {activos} productos activos en la base.")


if __name__ == "__main__":
    main()
