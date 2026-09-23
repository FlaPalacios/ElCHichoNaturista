// Cómo está configurado este despliegue. Lo que cambia entre la laptop, el
// servidor de muestra y el definitivo vive acá y no repartido por el código.

/**
 * Cuánto se espera a que la API conteste, en milisegundos.
 *
 * En el servidor el margen es amplio a propósito: en un plan gratuito la API
 * se apaga tras un rato sin visitas y tarda cerca de un minuto en volver. Si
 * se corta antes, la primera visita del día ve el aviso de "tienda no
 * disponible" aunque no haya nada roto. En el navegador el margen es corto:
 * ahí la API ya despertó al pintar la página, y un minuto en blanco frente a
 * un botón se siente como que la página se colgó.
 */
export const ESPERA = import.meta.env.SSR ? 55000 : 12000;

/**
 * true mientras el sitio sea una muestra para recoger opiniones.
 *
 * Con esto puesto se le pide a los buscadores que no lo indexen: el catálogo
 * está a medias y los precios no son definitivos, y una vez que Google guarda
 * una página cuesta semanas sacarla. Se apaga borrando la variable
 * SITIO_DEMO del servidor, sin tocar el código.
 *
 * El `typeof` no sobra: este archivo también viaja al navegador por culpa de
 * ESPERA, y ahí `process` no existe.
 */
export const ES_DEMO =
  typeof process !== 'undefined' && process.env?.SITIO_DEMO === 'true';
