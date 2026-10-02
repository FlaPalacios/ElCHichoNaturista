"""Los ajustes de la tienda: qué se puede editar desde el panel y su valor.

Viven en la tabla `configuracion` como clave-valor. Los valores por defecto de
acá son los que se usan mientras nadie los haya cambiado, así una instalación
nueva funciona sin configurar nada.
"""

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ajustes
from app.models import Configuracion

# clave -> (valor por defecto, tipo)
AJUSTES: dict[str, tuple[str, str]] = {
    "nombre": ("El Chico Naturista", "texto"),
    "lema": ("Productos naturales del Perú", "texto"),
    "whatsapp": ("51946049689", "texto"),
    "whatsapp_visible": ("+51 946 049 689", "texto"),
    "correo": ("hola@elchiconaturista.pe", "texto"),
    "direccion": ("Las Camelias, Mz. K Lt. 17 – Los Olivos, Lima", "texto"),
    "horario": ("Lunes a sábado · 9:00 a 19:00", "texto"),
    "tiktok": ("https://www.tiktok.com/@el.chico.naturista", "texto"),
    "linkedin": (
        "https://www.linkedin.com/company/el-chico-naturista/posts/?feedView=all",
        "texto",
    ),
    "metodos_pago": (
        "Puedes pagar con Yape, Plin o transferencia bancaria. "
        "Te pasamos los datos por WhatsApp al confirmar.",
        "texto_largo",
    ),
    "plantilla_whatsapp": (
        "Hola {tienda}, quiero confirmar mi pedido {numero}.",
        "texto_largo",
    ),
    "avisos": (
        "Envíos a todo el Perú · Delivery el mismo día en Lima\n"
        "Pedidos coordinados por WhatsApp, sin pasarela de pago\n"
        "Envío gratis en todo el Perú desde S/ 120",
        "lineas",
    ),
    "envio_gratis_desde": (str(ajustes.envio_gratis_desde), "numero"),
    "stock_bajo": (str(ajustes.stock_bajo), "entero"),
}


def leer_todo(sesion: Session) -> dict[str, str]:
    """Los ajustes guardados, con los valores por defecto para los que falten."""
    guardados = {
        c.clave: c.valor for c in sesion.scalars(select(Configuracion))
    }
    return {
        clave: guardados.get(clave, defecto) for clave, (defecto, _) in AJUSTES.items()
    }


def guardar(sesion: Session, valores: dict[str, str]) -> dict[str, str]:
    """Guarda solo las claves conocidas; las demás se ignoran."""
    for clave, valor in valores.items():
        if clave not in AJUSTES:
            continue
        fila = sesion.get(Configuracion, clave)
        if fila is None:
            fila = Configuracion(clave=clave)
            sesion.add(fila)
        fila.valor = str(valor)
    sesion.flush()
    return leer_todo(sesion)


def numero(sesion: Session, clave: str) -> Decimal:
    """Un ajuste numérico, cayendo al valor por defecto si quedó mal escrito."""
    crudo = leer_todo(sesion).get(clave, AJUSTES[clave][0])
    try:
        return Decimal(crudo)
    except (InvalidOperation, TypeError):
        return Decimal(AJUSTES[clave][0])


def entero(sesion: Session, clave: str) -> int:
    try:
        return int(leer_todo(sesion).get(clave, AJUSTES[clave][0]))
    except (ValueError, TypeError):
        return int(AJUSTES[clave][0])
