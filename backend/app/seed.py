"""Carga el catálogo real desde las planillas de `app/datos`.

    python -m app.seed            # crea o actualiza (idempotente)
    python -m app.seed --reset    # borra el catálogo y lo vuelve a cargar

Las planillas son la fuente de verdad del catálogo y se editan a mano
(Excel, Google Sheets → exportar como TSV):

    datos/marcas.tsv        slug, nombre, orden
    datos/categorias.tsv    slug, nombre, orden del menú, activo
    datos/subcategorias.tsv slug, nombre, de qué categoría cuelga, orden, activo
    datos/catalogo.tsv      un producto por fila, identificado por `codigo`
    datos/imagenes.tsv      las fotos de Cloudinary de cada `codigo`

Un producto sin precio confirmado se carga con `precio 0.00` y `activo=false`:
queda en la base como borrador y no aparece en la tienda hasta que se complete
y se active desde el panel.

**El panel es la fuente de verdad del catálogo.** Este comando solo crea lo que
falta: si un producto ya está en la base, no lo toca. Para reemplazar todo a
propósito está `--reset`, que borra y vuelve a cargar. Para cargar cambios masivos
desde una planilla, usa Importar en el panel.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import SesionLocal
from app.models import (
    Categoria,
    ImagenProducto,
    Marca,
    PedidoItem,
    Producto,
    Subcategoria,
)

CARPETA_DATOS = Path(__file__).parent / "datos"


def leer_tsv(nombre: str) -> list[dict[str, str]]:
    archivo = CARPETA_DATOS / nombre
    if not archivo.exists():
        raise SystemExit(f"Falta la planilla {archivo}.")
    with archivo.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f, delimiter="\t")
        # Descarta las filas en blanco que suele dejar Excel al exportar.
        filas = [fila for fila in lector if any(fila.values())]

    # Una fila con más o menos tabulaciones que la cabecera corre todos los
    # valores de sitio y el error salta mucho después, sin decir dónde.
    for numero, fila in enumerate(filas, start=2):
        if None in fila or None in fila.values():
            raise SystemExit(
                f"{nombre}, línea {numero}: tiene {len(fila)} columnas y la "
                f"cabecera {len(lector.fieldnames)}. Revisa las tabulaciones."
            )
    return filas


def _texto(fila: dict[str, str], clave: str) -> str | None:
    """Celda vacía del TSV → None, para no guardar cadenas vacías en la base."""
    valor = (fila.get(clave) or "").strip()
    return valor or None


def _booleano(fila: dict[str, str], clave: str) -> bool:
    return (fila.get(clave) or "").strip().lower() == "true"


def sembrar_marcas(sesion: Session) -> dict[str, Marca]:
    """Crea o actualiza marcas por slug. Devuelve el mapa slug -> Marca."""
    filas = leer_tsv("marcas.tsv")
    por_slug: dict[str, Marca] = {}
    nuevas = 0

    for fila in filas:
        slug = fila["slug"].strip()
        marca = sesion.scalar(select(Marca).where(Marca.slug == slug))
        if marca is None:
            marca = Marca(slug=slug)
            sesion.add(marca)
            nuevas += 1
        marca.nombre = fila["nombre"].strip()
        marca.orden = int(fila["orden"])
        por_slug[slug] = marca

    sesion.flush()
    print(f"  marcas:     {len(filas)} procesadas ({nuevas} nuevas)")
    return por_slug


def sembrar_categorias(sesion: Session) -> dict[str, Categoria]:
    """Crea o actualiza categorías por slug. Devuelve el mapa slug -> Categoria."""
    filas = leer_tsv("categorias.tsv")
    por_slug: dict[str, Categoria] = {}
    nuevas = 0

    for fila in filas:
        slug = fila["slug"].strip()
        categoria = sesion.scalar(select(Categoria).where(Categoria.slug == slug))
        if categoria is None:
            categoria = Categoria(slug=slug)
            sesion.add(categoria)
            nuevas += 1
        categoria.nombre = fila["nombre"].strip()
        categoria.orden = int(fila["orden"])
        categoria.activo = _booleano(fila, "activo")
        por_slug[slug] = categoria

    sesion.flush()
    print(f"  categorías: {len(filas)} procesadas ({nuevas} nuevas)")
    return por_slug


def sembrar_subcategorias(
    sesion: Session, categorias: dict[str, Categoria]
) -> dict[str, Subcategoria]:
    filas = leer_tsv("subcategorias.tsv")
    por_slug: dict[str, Subcategoria] = {}
    nuevas = 0

    for fila in filas:
        slug = fila["slug"].strip()
        categoria = categorias.get(fila["categoria_slug"].strip())
        if categoria is None:
            raise SystemExit(
                f"La subcategoría '{slug}' apunta a la categoría "
                f"'{fila['categoria_slug']}', que no está en categorias.tsv."
            )

        sub = sesion.scalar(select(Subcategoria).where(Subcategoria.slug == slug))
        if sub is None:
            sub = Subcategoria(slug=slug)
            sesion.add(sub)
            nuevas += 1
        sub.nombre = fila["nombre"].strip()
        sub.categoria_id = categoria.id
        sub.orden = int(fila["orden"])
        sub.activo = _booleano(fila, "activo")
        por_slug[slug] = sub

    sesion.flush()
    print(f"  subcategorías: {len(filas)} procesadas ({nuevas} nuevas)")
    return por_slug


def sembrar_productos(
    sesion: Session, marcas: dict[str, Marca], subcategorias: dict[str, Subcategoria]
) -> None:
    filas = leer_tsv("catalogo.tsv")
    nuevos = 0
    borradores = 0
    respetados = 0

    for fila in filas:
        codigo = fila["codigo"].strip()
        marca = marcas.get(fila["marca_slug"].strip())
        if marca is None:
            raise SystemExit(
                f"El producto '{codigo}' apunta a la marca "
                f"'{fila['marca_slug']}', que no está en marcas.tsv."
            )
        sub = subcategorias.get(fila["subcategoria_slug"].strip())
        if sub is None:
            raise SystemExit(
                f"El producto '{codigo}' apunta a la subcategoría "
                f"'{fila['subcategoria_slug']}', que no está en subcategorias.tsv."
            )

        producto = sesion.scalar(select(Producto).where(Producto.codigo == codigo))
        if producto is not None:
            # El panel es la fuente de verdad del catálogo: un producto que ya
            # está en la base no se toca, para no pisar lo que Fernando editó.
            # Para reemplazarlo todo a propósito está --reset.
            respetados += 1
            continue
        producto = Producto(codigo=codigo)
        sesion.add(producto)
        nuevos += 1

        producto.nombre = fila["nombre"].strip()
        producto.slug = fila["slug"].strip()
        producto.marca_id = marca.id
        producto.subcategoria_id = sub.id
        producto.descripcion_corta = _texto(fila, "descripcion_corta")
        producto.descripcion_larga = _texto(fila, "descripcion_larga")
        producto.modo_uso = _texto(fila, "modo_uso")
        producto.presentacion = _texto(fila, "presentacion")
        beneficios = _texto(fila, "beneficios")
        producto.beneficios = beneficios.split("|") if beneficios else []
        producto.precio = Decimal(fila["precio"].strip() or "0")
        precio_antes = _texto(fila, "precio_antes")
        producto.precio_antes = Decimal(precio_antes) if precio_antes else None
        producto.stock = int(fila["stock"] or 0)
        producto.activo = _booleano(fila, "activo")
        producto.destacado = _booleano(fila, "destacado")
        producto.mas_vendido = _booleano(fila, "mas_vendido")

        if not producto.activo:
            borradores += 1

    sesion.flush()
    resumen = f"  productos:  {len(filas)} en la planilla ({nuevos} nuevos, {borradores} borradores)"
    if respetados:
        resumen += f"\n              {respetados} ya estaban en la base y no se tocaron"
    print(resumen)


def sembrar_imagenes(sesion: Session) -> None:
    """Reemplaza las imágenes de cada producto por las de la planilla."""
    filas = leer_tsv("imagenes.tsv")
    codigos = {c for (c,) in sesion.execute(select(Producto.codigo))}

    huerfanas = {f["id_producto"].strip() for f in filas} - codigos
    if huerfanas:
        raise SystemExit(
            "imagenes.tsv tiene fotos de productos que no están en "
            f"catalogo.tsv: {', '.join(sorted(huerfanas))}."
        )

    # Igual que con los productos: solo se agregan las fotos que faltan.
    ya_tienen = {
        c for (c,) in sesion.execute(select(ImagenProducto.id_producto).distinct())
    }
    filas = [f for f in filas if f["id_producto"].strip() not in ya_tienen]
    for fila in filas:
        sesion.add(
            ImagenProducto(
                id_producto=fila["id_producto"].strip(),
                url=fila["url"].strip(),
                orden=int(fila["orden"]),
                tipo=_texto(fila, "tipo"),
            )
        )

    sesion.flush()
    con_foto = len({f["id_producto"] for f in filas})
    print(f"  imágenes:   {len(filas)} nuevas en {con_foto} productos")


def limpiar(sesion: Session) -> None:
    """Borra el catálogo. No toca pedidos si ya hay alguno que dependa de él."""
    if sesion.scalar(select(PedidoItem).limit(1)) is not None:
        raise SystemExit(
            "Hay pedidos con items en la base: --reset borraría productos "
            "referenciados. Limpia los pedidos primero."
        )
    sesion.execute(delete(ImagenProducto))
    sesion.execute(delete(Producto))
    sesion.execute(delete(Subcategoria))
    sesion.execute(delete(Categoria))
    sesion.execute(delete(Marca))
    sesion.flush()
    print("  catálogo anterior borrado")


def main() -> None:
    analizador = argparse.ArgumentParser(description="Carga el catálogo real.")
    analizador.add_argument(
        "--reset",
        action="store_true",
        help="borra categorías, productos e imágenes antes de cargar",
    )
    argumentos = analizador.parse_args()

    print("Sembrando catálogo de El Chico Naturista…")
    with SesionLocal() as sesion:
        if argumentos.reset:
            limpiar(sesion)

        marcas = sembrar_marcas(sesion)
        categorias = sembrar_categorias(sesion)
        subcategorias = sembrar_subcategorias(sesion, categorias)
        sembrar_productos(sesion, marcas, subcategorias)
        sembrar_imagenes(sesion)
        sesion.commit()

        activos = sesion.scalar(
            select(func.count()).select_from(Producto).where(Producto.activo.is_(True))
        )
        print(f"Listo. {activos} productos activos en la base.")


if __name__ == "__main__":
    main()
