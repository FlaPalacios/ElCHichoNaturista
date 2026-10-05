"""Subida y borrado de fotos en Cloudinary.

Las credenciales van en el `.env` (`CLOUDINARY_*`). Si no están puestas, la
subida responde un error claro en vez de fallar de forma rara: el resto del
panel sigue funcionando igual.
"""

import secrets

import cloudinary
import cloudinary.api
import cloudinary.uploader

from app.config import ajustes

CARPETA = "elchiconaturista/productos"
TIPOS_PERMITIDOS = {"image/jpeg", "image/png", "image/webp", "image/avif"}
PESO_MAXIMO = 8 * 1024 * 1024  # 8 MB


class ErrorFoto(Exception):
    """Algo impidió guardar la foto. La ruta lo traduce a HTTP."""


def _configurar() -> None:
    if not ajustes.cloudinary_configurado:
        raise ErrorFoto(
            "Faltan las credenciales de Cloudinary en el .env "
            "(CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET)."
        )
    cloudinary.config(
        cloud_name=ajustes.cloudinary_cloud_name,
        api_key=ajustes.cloudinary_api_key,
        api_secret=ajustes.cloudinary_api_secret,
        secure=True,
    )


def subir(contenido: bytes, *, codigo: str, orden: int, tipo_mime: str) -> dict:
    """Sube la foto y devuelve su URL y su identificador en Cloudinary."""
    if tipo_mime not in TIPOS_PERMITIDOS:
        raise ErrorFoto(
            f"Formato no admitido ({tipo_mime}). Usa JPG, PNG, WebP o AVIF."
        )
    if len(contenido) > PESO_MAXIMO:
        raise ErrorFoto("La foto pesa más de 8 MB. Recórtala o bájale la calidad.")

    _configurar()
    # El nombre lleva el código del producto para reconocerlo desde el panel de
    # Cloudinary; el sufijo al azar evita pisar una foto que ya esté ahí.
    nombre = f"{codigo}-{orden}-{secrets.token_hex(3)}"
    try:
        resultado = cloudinary.uploader.upload(
            contenido,
            folder=CARPETA,
            public_id=nombre,
            overwrite=False,
            resource_type="image",
        )
    except Exception as error:  # la librería lanza varios tipos distintos
        raise ErrorFoto(f"Cloudinary rechazó la subida: {error}") from error

    return {"url": resultado["secure_url"], "public_id": resultado["public_id"]}


def borrar(public_id: str) -> None:
    """Borra la foto de Cloudinary. No falla si ya no estaba.

    `invalidate` purga además la copia que el CDN tenga cacheada; sin eso la
    URL sigue respondiendo un buen rato después de borrar el archivo.
    """
    _configurar()
    try:
        cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)
    except Exception as error:
        raise ErrorFoto(f"No se pudo borrar la foto en Cloudinary: {error}") from error


def public_id_desde_url(url: str) -> str | None:
    """Saca el identificador de una URL de Cloudinary ya guardada.

    Las fotos que se cargaron con la planilla no tienen `public_id` anotado, así
    que se deduce de la URL:
    https://res.cloudinary.com/<cuenta>/image/upload/v123/carpeta/archivo.webp
    """
    marca = "/image/upload/"
    if marca not in url:
        return None
    cola = url.split(marca, 1)[1]
    partes = [p for p in cola.split("/") if not (p.startswith("v") and p[1:].isdigit())]
    if not partes:
        return None
    ruta = "/".join(partes)
    return ruta.rsplit(".", 1)[0] if "." in ruta.rsplit("/", 1)[-1] else ruta


MAX_BIBLIOTECA = 1000


def listar() -> list[dict]:
    """Todas las fotos de la cuenta de Cloudinary, las más nuevas primero.

    Se pide sin carpeta porque las primeras fotos (las de la planilla) se
    subieron sin ella. Tope de 1000 para que la pantalla no se ponga lenta.
    """
    _configurar()
    fotos_cloudinary: list[dict] = []
    cursor = None
    try:
        while len(fotos_cloudinary) < MAX_BIBLIOTECA:
            pagina = cloudinary.api.resources(
                resource_type="image", type="upload", max_results=500, next_cursor=cursor
            )
            fotos_cloudinary.extend(pagina.get("resources", []))
            cursor = pagina.get("next_cursor")
            if not cursor:
                break
    except Exception as error:
        raise ErrorFoto(f"No se pudo leer la biblioteca de Cloudinary: {error}") from error

    fotos_cloudinary.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    return fotos_cloudinary


def obtener(public_id: str) -> dict:
    """Los datos de una foto que ya está en Cloudinary (y confirma que existe)."""
    _configurar()
    try:
        return cloudinary.api.resource(public_id, resource_type="image")
    except Exception as error:
        raise ErrorFoto(f"Esa foto no existe en Cloudinary: {error}") from error
