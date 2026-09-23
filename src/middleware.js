// Carga los datos de la tienda una vez por visita y los deja en
// `Astro.locals.tienda`, para que el encabezado, el pie y las páginas no
// tengan que pedirlos cada uno por su cuenta.
import { ES_DEMO } from './lib/entorno.js';
import { cargarTienda } from './lib/tienda.js';

export async function onRequest(contexto, siguiente) {
  // Las rutas de API no pintan nada de la tienda: se saltan la consulta.
  if (!contexto.url.pathname.startsWith('/api/')) {
    contexto.locals.tienda = await cargarTienda();
  }
  const respuesta = await siguiente();
  // El robots.txt frena al buscador que lo respeta; esta cabecera cubre al
  // que llega por un enlace compartido sin pasar por ahí.
  if (ES_DEMO) respuesta.headers.set('X-Robots-Tag', 'noindex, nofollow');
  return respuesta;
}
