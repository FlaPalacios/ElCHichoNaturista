"""Importar productos desde una planilla TSV.

Todo el trabajo vive acá para que el endpoint solo se ocupe de HTTP. La regla
es que ninguna fila mala rompa el proceso con un error 500: cada problema se
convierte en un mensaje con su línea, y se reportan todos juntos.

Cada fila pasa por los mismos esquemas Pydantic que el formulario del panel
(`ProductoCrear`/`ProductoEntrada`), así la planilla no puede colar nada que el
panel rechazaría (precios incoherentes, textos largos, slugs inválidos).
"""

import csv
import io
import re
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.models import Marca, Subcategoria
from app.schemas import ProductoCrear, ProductoEntrada

COLUMNAS = [
    "codigo", "nombre", "slug", "marca_slug", "categoria_slug", "subcategoria_slug",
    "precio", "precio_antes", "presentacion", "descripcion_corta", "descripcion_larga",
    "modo_uso", "beneficios", "stock", "activo", "destacado", "mas_vendido",
]
# Sin estas el producto no se puede crear. `categoria_slug` no hace falta: la
# categoría sale de la subcategoría.
OBLIGATORIAS = [
    "codigo", "nombre", "slug", "marca_slug", "subcategoria_slug", "precio", "stock",
]
MAX_BYTES = 2 * 1024 * 1024
MAX_FILAS = 1000

_SI = {"true", "verdadero", "si", "sí", "1", "x", "yes", "activo"}
_NO = {"false", "falso", "no", "0", "inactivo"}


class ErrorPlanilla(Exception):
    """La planilla entera no sirve (vacía, sin columnas, ilegible)."""


def leer_planilla(contenido: bytes) -> tuple[list[dict[str, str]], list[str]]:
    """Devuelve las filas como diccionarios y los avisos que merezcan mostrarse."""
    if len(contenido) > MAX_BYTES:
        raise ErrorPlanilla("El archivo pesa más de 2 MB; no parece una planilla de catálogo.")

    avisos: list[str] = []
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel en Windows guarda en cp1252 cuando se exporta como "texto".
        texto = contenido.decode("cp1252", errors="replace")
        avisos.append("El archivo no estaba en UTF-8; se leyó como Windows-1252.")

    if not texto.strip():
        raise ErrorPlanilla("El archivo está vacío.")

    primera = texto.split("\n", 1)[0]
    delimitador = "\t"
    if "\t" not in primera:
        for candidato in (";", ","):
            if candidato in primera:
                delimitador = candidato
                avisos.append("El archivo no usa tabuladores; se leyó separado por «%s»." % candidato)
                break

    lector = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    cabecera = [(c or "").strip().lower() for c in (lector.fieldnames or [])]
    faltan = [c for c in OBLIGATORIAS if c not in cabecera]
    if faltan:
        raise ErrorPlanilla(
            "Faltan columnas en la primera fila: %s. Descarga «Exportar TSV» y úsala de modelo."
            % ", ".join(faltan)
        )

    filas = []
    for crudo in lector:
        fila = {(k or "").strip().lower(): (v or "").strip() for k, v in crudo.items()}
        # Excel deja filas vacías al final.
        if any(fila.values()):
            filas.append(fila)
    if not filas:
        raise ErrorPlanilla("La planilla no tiene filas de productos.")
    if len(filas) > MAX_FILAS:
        raise ErrorPlanilla("La planilla tiene más de %d filas." % MAX_FILAS)
    return filas, avisos


def _decimal(texto: str, campo: str) -> Decimal | None:
    if not texto:
        return None
    limpio = re.sub(r"^(s/\.?|\$)\s*", "", texto.strip(), flags=re.I).replace(" ", "")
    # «1.234,50» o «22,80»: la coma es el decimal.
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        raise ValueError("%s: «%s» no es un número." % (campo, texto)) from None


def _entero(texto: str, campo: str) -> int:
    if not texto:
        return 0
    try:
        numero = Decimal(texto.replace(",", "."))
    except InvalidOperation:
        raise ValueError("%s: «%s» no es un número entero." % (campo, texto)) from None
    if numero != numero.to_integral_value():
        raise ValueError("%s: «%s» debe ser un número entero." % (campo, texto))
    return int(numero)


def _booleano(texto: str, campo: str, vigente: bool) -> bool:
    """Una celda vacía deja el valor que ya tenía el producto (o el de por
    defecto si es nuevo): vaciarla por descuido no debe desactivar nada."""
    if not texto:
        return vigente
    valor = texto.strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    raise ValueError("%s: «%s» no se entiende; usa true o false." % (campo, texto))


_ESPANOL = {
    "string_too_short": lambda c: "mínimo %s caracteres" % c.get("min_length"),
    "string_too_long": lambda c: "máximo %s caracteres" % c.get("max_length"),
    "too_long": lambda c: "máximo %s elementos" % c.get("max_length"),
    "string_pattern_mismatch": lambda c: "formato no válido",
    "greater_than_equal": lambda c: "no puede ser menor que %s" % c.get("ge"),
    "less_than_equal": lambda c: "no puede ser mayor que %s" % c.get("le"),
}


def _mensaje_pydantic(error: ValidationError) -> str:
    partes = []
    for e in error.errors():
        donde = ".".join(str(p) for p in e["loc"])
        traduce = _ESPANOL.get(e["type"])
        texto = traduce(e.get("ctx", {})) if traduce else e["msg"].removeprefix("Value error, ")
        partes.append("%s: %s" % (donde, texto) if donde else texto)
    return "; ".join(partes)


def procesar(sesion: Session, filas: list[dict[str, str]], *, aplicar: bool) -> dict:
    """Valida y, si `aplicar`, guarda. Siempre devuelve el mismo resumen.

    Con `aplicar=False` se hace todo igual pero se deshace al final: sirve de
    vista previa fiable, porque corre exactamente las mismas comprobaciones.
    Con `aplicar=True` solo se guarda si no hubo ningún error."""
    # Lo que está en la papelera no cuenta: no se le pueden colgar productos.
    marcas = {
        m.slug: m.id
        for m in sesion.scalars(select(Marca).where(Marca.eliminado_en.is_(None)))
    }
    subcategorias = {
        s.slug: s.id
        for s in sesion.scalars(
            select(Subcategoria).where(Subcategoria.eliminado_en.is_(None))
        )
    }
    creados: list[str] = []
    actualizados: list[str] = []
    errores: list[str] = []
    vistos: dict[str, int] = {}

    for numero, fila in enumerate(filas, start=2):
        codigo = fila.get("codigo", "").upper()
        ref = "Línea %d" % numero + (" (%s)" % codigo if codigo else "")

        if not codigo:
            errores.append("%s: falta el código." % ref)
            continue
        if codigo in vistos:
            errores.append("%s: el código ya aparece en la línea %d." % (ref, vistos[codigo]))
            continue
        vistos[codigo] = numero

        marca = fila.get("marca_slug", "")
        sub = fila.get("subcategoria_slug", "")
        if marca not in marcas:
            errores.append("%s: la marca «%s» no existe (créala antes en Marcas)." % (ref, marca))
            continue
        if sub not in subcategorias:
            errores.append(
                "%s: la subcategoría «%s» no existe (créala antes en Categorías)." % (ref, sub)
            )
            continue

        existente = crud.obtener_producto_admin(sesion, codigo)
        try:
            precio = _decimal(fila.get("precio", ""), "precio")
            if precio is None:
                raise ValueError("precio: falta el precio.")
            beneficios = [b.strip() for b in fila.get("beneficios", "").split("|") if b.strip()]
            datos = {
                "nombre": fila.get("nombre", ""),
                "slug": fila.get("slug", ""),
                "marca_id": marcas[marca],
                "subcategoria_id": subcategorias[sub],
                "precio": precio,
                "precio_antes": _decimal(fila.get("precio_antes", ""), "precio_antes"),
                # En un producto que ya existe el stock se ignora (ver abajo),
                # así que una celda mal escrita no debe frenar la fila.
                "stock": 0 if existente else _entero(fila.get("stock", ""), "stock"),
                "activo": _booleano(fila.get("activo", ""), "activo", existente.activo if existente else True),
                "destacado": _booleano(fila.get("destacado", ""), "destacado", existente.destacado if existente else False),
                "mas_vendido": _booleano(fila.get("mas_vendido", ""), "mas_vendido", existente.mas_vendido if existente else False),
                "presentacion": fila.get("presentacion") or None,
                "descripcion_corta": fila.get("descripcion_corta") or None,
                "descripcion_larga": fila.get("descripcion_larga") or None,
                "modo_uso": fila.get("modo_uso") or None,
                "beneficios": beneficios,
            }
            if existente is None:
                datos = ProductoCrear(**datos, codigo=codigo).model_dump()
            else:
                datos = ProductoEntrada(**datos).model_dump()
                # El stock lo manda la web (pedidos, compras, ajustes): la
                # planilla solo lo usa para dar de alta un producto nuevo.
                datos.pop("stock")
        except ValueError as error:  # incluye ValidationError
            detalle = (
                _mensaje_pydantic(error) if isinstance(error, ValidationError) else str(error)
            )
            errores.append("%s: %s" % (ref, detalle))
            continue

        try:
            crud.guardar_producto(sesion, datos, producto=existente)
        except crud.ErrorCatalogo as error:
            errores.append("%s: %s" % (ref, error))
            continue
        (creados if existente is None else actualizados).append(codigo)

    if aplicar and not errores:
        sesion.commit()
    else:
        sesion.rollback()

    return {
        "aplicado": aplicar and not errores,
        "creados": len(creados),
        "actualizados": len(actualizados),
        "codigos_nuevos": creados,
        "filas_con_error": len(errores),
        "errores": errores,
    }
