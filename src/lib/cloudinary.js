// Las URLs que guarda la base son las que devuelve Cloudinary al subir:
//   https://res.cloudinary.com/<cuenta>/image/upload/v123/archivo.webp
// Insertando transformaciones después de `/upload/` se pide esa misma foto ya
// redimensionada y en el formato que mejor soporte el navegador, sin tocar el
// original ni guardar varias URLs.

const MARCA_SUBIDA = '/image/upload/';

/** Misma foto servida al ancho pedido. Si la URL no es de Cloudinary, la deja igual. */
export function urlCloudinary(url, ancho) {
  const corte = url.indexOf(MARCA_SUBIDA);
  if (corte === -1) return url;

  const inicio = corte + MARCA_SUBIDA.length;
  return `${url.slice(0, inicio)}f_auto,q_auto,c_limit,w_${ancho}/${url.slice(inicio)}`;
}
