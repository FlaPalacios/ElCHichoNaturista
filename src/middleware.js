// Carga los datos de la tienda una vez por visita y los deja en
// `Astro.locals.tienda`, para que el encabezado, el pie y las páginas no
// tengan que pedirlos cada uno por su cuenta.
import { cargarTienda } from './lib/tienda.js';

export async function onRequest(contexto, siguiente) {
  // Las rutas de API no pintan nada de la tienda: se saltan la consulta.
  if (!contexto.url.pathname.startsWith('/api/')) {
    contexto.locals.tienda = await cargarTienda();
  }
  return siguiente();
}
