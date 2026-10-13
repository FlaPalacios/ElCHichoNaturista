"""Carga única de las ventas hechas antes de la web (V-001, V-002…).

    python -m app.ventas_antiguas ../recursos-/ECN-Ventas.csv            # vista previa
    python -m app.ventas_antiguas ../recursos-/ECN-Ventas.csv --aplicar  # guarda

Lee el mismo formato que la exportación de pedidos (una fila por producto) y
también el de la planilla de ventas anterior: «Fecha» en vez de «Fecha
pedido», precios con «S/ » y fechas DD/MM/AAAA.

Cada pedido entra como `completado`, origen `manual`, con sus fechas y sus
precios. Su número V-NNN pasa a ser su número de venta (`correlativo`) y recibe
un código de pedido ECN-M-AAMMDD-NNNN, como cualquier venta manual. **No toca el stock**: esas ventas ya ocurrieron y el stock se ajusta
aparte. Es idempotente: un número de venta que ya existe se salta.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import crud
from app.database import SesionLocal
from app.exportar import CODIGO_ENVIO, LIMA
from app.models import EstadoPedido, Pedido, PedidoItem, Producto

# A qué hora se fecha una venta de la que solo se sabe el día: el mediodía
# evita que un cambio de zona la mueva al día anterior o siguiente.
MEDIODIA = time(12, 0)


class ErrorArchivo(Exception):
    pass


@dataclass
class Venta:
    numero: str
    cliente: str = ""
    fecha: date | None = None
    fecha_pago: date | None = None
    envio: Decimal = Decimal("0.00")
    lineas: list[tuple[str, int, Decimal]] = field(default_factory=list)  # código, cantidad, precio

    @property
    def subtotal(self) -> Decimal:
        return sum((c * p for _, c, p in self.lineas), Decimal("0.00"))


def _columna(cabecera: list[str], *nombres: str, obligatoria: bool = True) -> int | None:
    normal = [c.strip().lower() for c in cabecera]
    for nombre in nombres:
        if nombre.lower() in normal:
            return normal.index(nombre.lower())
    if obligatoria:
        raise ErrorArchivo(f"Falta la columna «{nombres[0]}».")
    return None


def _fecha(texto: str) -> date | None:
    texto = texto.strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    raise ValueError(f"fecha «{texto}» no se entiende (usa AAAA-MM-DD)")


def _precio(texto: str) -> Decimal:
    limpio = re.sub(r"^s/\.?\s*", "", texto.strip(), flags=re.I).replace(",", "")
    try:
        return Decimal(limpio).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"precio «{texto}» no es un número") from None


def _numero(texto: str) -> str:
    """V-9 o V-09 → V-009, para que ordenen bien y coincidan con el Sheet."""
    texto = texto.strip().upper()
    m = re.fullmatch(r"V-(\d+)", texto)
    return f"V-{int(m.group(1)):03d}" if m else texto


def _correlativo(numero: str) -> int | None:
    m = re.fullmatch(r"V-(\d+)", numero)
    return int(m.group(1)) if m else None


def leer(ruta: Path) -> list[Venta]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.reader(archivo))
    if not filas:
        raise ErrorArchivo("El archivo está vacío.")

    cab = filas[0]
    i_num = _columna(cab, "N° pedido")
    i_fecha = _columna(cab, "Fecha pedido", "Fecha")
    i_pago = _columna(cab, "Fecha pago", obligatoria=False)
    i_cliente = _columna(cab, "Cliente")
    i_codigo = _columna(cab, "Código")
    i_cant = _columna(cab, "Cantidad")
    i_precio = _columna(cab, "Precio unitario", "Precio unitario (S/)")

    ventas: dict[str, Venta] = {}
    errores = []
    for linea, fila in enumerate(filas[1:], start=2):
        if not any(c.strip() for c in fila):
            continue  # separadores en blanco
        try:
            venta = ventas.setdefault(_numero(fila[i_num]), Venta(_numero(fila[i_num])))
            venta.cliente = venta.cliente or fila[i_cliente].strip()
            venta.fecha = venta.fecha or _fecha(fila[i_fecha])
            if i_pago is not None:
                venta.fecha_pago = venta.fecha_pago or _fecha(fila[i_pago])
            codigo = fila[i_codigo].strip().upper()
            cantidad = int(fila[i_cant])
            precio = _precio(fila[i_precio])
            if codigo == CODIGO_ENVIO:
                venta.envio = precio * cantidad
            else:
                venta.lineas.append((codigo, cantidad, precio))
        except (ValueError, IndexError) as error:
            errores.append(f"Línea {linea}: {error}")
    if errores:
        raise ErrorArchivo("\n".join(errores))
    return list(ventas.values())


def cargar(sesion: Session, ventas: list[Venta], *, fecha_por_defecto: date | None) -> dict:
    """Crea los pedidos que falten. No hace commit: lo decide quien llama."""
    productos = {p.codigo: p for p in sesion.scalars(select(Producto))}
    # Número de venta → (código de pedido, origen) de lo que ya está en la base.
    usados = {
        c: (n, o)
        for c, n, o in sesion.execute(
            select(Pedido.correlativo, Pedido.numero_pedido, Pedido.origen)
        )
    }
    creados, saltados, errores = [], [], []

    for v in ventas:
        correlativo = _correlativo(v.numero)
        if correlativo in usados and usados[correlativo][1] == "manual":
            saltados.append(v.numero)  # ya se cargó antes
            continue
        fecha = v.fecha or fecha_por_defecto
        faltan = [c for c, _, _ in v.lineas if c not in productos]
        if correlativo is None:
            errores.append(f"{v.numero}: el número debe tener la forma V-001.")
        elif correlativo in usados:
            errores.append(
                f"{v.numero}: ese número de venta ya lo tiene el pedido web {usados[correlativo][0]}."
            )
        elif fecha is None:
            errores.append(f"{v.numero}: no tiene fecha; pasa --fecha AAAA-MM-DD.")
        elif not v.cliente:
            errores.append(f"{v.numero}: no tiene cliente.")
        elif not v.lineas:
            errores.append(f"{v.numero}: no tiene productos.")
        elif faltan:
            errores.append(f"{v.numero}: códigos que no existen en la web: {', '.join(faltan)}.")
        if errores and errores[-1].startswith(v.numero):
            continue

        momento = datetime.combine(fecha, MEDIODIA, tzinfo=LIMA)
        pago = datetime.combine(v.fecha_pago, MEDIODIA, tzinfo=LIMA) if v.fecha_pago else momento
        pedido = Pedido(
            numero_pedido=crud.generar_numero_pedido(sesion, prefijo="ECN-M", dia=fecha),
            correlativo=correlativo,
            origen="manual",
            nombre_contacto=v.cliente,
            estado=EstadoPedido.completado,
            envio=v.envio,
            total=v.subtotal + v.envio,
            creado_en=momento,
            fecha_pago=pago,
        )
        for codigo, cantidad, precio in v.lineas:
            pedido.items.append(
                PedidoItem(
                    producto_id=productos[codigo].id, cantidad=cantidad, precio_unitario=precio
                )
            )
        sesion.add(pedido)
        sesion.flush()  # para que el próximo código generado vea este
        creados.append(v.numero)

    if creados:
        # Los números se pusieron a mano: la secuencia debe seguir después del
        # mayor, para que el próximo pedido de la web no choque.
        mayor = sesion.scalar(select(func.max(Pedido.correlativo)))
        sesion.execute(
            text("SELECT setval('pedidos_correlativo_seq', :n)"), {"n": mayor}
        )
    return {"creados": creados, "saltados": saltados, "errores": errores}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--fecha", type=date.fromisoformat, help="Para filas sin fecha.")
    parser.add_argument("--aplicar", action="store_true", help="Guarda; sin esto es vista previa.")
    args = parser.parse_args()

    try:
        ventas = leer(args.archivo)
    except (OSError, ErrorArchivo) as error:
        print(f"No se pudo leer el archivo:\n{error}", file=sys.stderr)
        return 1

    with SesionLocal() as sesion:
        r = cargar(sesion, ventas, fecha_por_defecto=args.fecha)
        for e in r["errores"]:
            print("  ERROR", e)
        aplicar = args.aplicar and not r["errores"]
        if aplicar:
            sesion.commit()
        else:
            sesion.rollback()

    print(f"  {len(ventas)} pedidos en el archivo")
    print(f"  {len(r['creados'])} nuevos: {', '.join(r['creados']) or '-'}")
    print(f"  {len(r['saltados'])} ya estaban: {', '.join(r['saltados']) or '-'}")
    if aplicar:
        print("Guardado. El stock no se modificó.")
    elif r["errores"]:
        print("No se guardó nada: corrige los errores.")
    else:
        print("Vista previa: nada se guardó. Repite con --aplicar.")
    return 1 if r["errores"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
