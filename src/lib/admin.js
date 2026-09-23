// Sesión del panel. El token JWT vive en una cookie httpOnly: el JavaScript
// del navegador no puede leerlo, así que las páginas del panel piden los datos
// desde el servidor y las modificaciones pasan por /api/admin/…, que reenvía a
// FastAPI poniendo el token.

const BASE = (
  import.meta.env.PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '');

export const COOKIE = 'ecn_sesion';

export const opcionesCookie = {
  httpOnly: true,
  sameSite: 'lax',
  path: '/',
  secure: import.meta.env.PROD,
};

/** Llama a la API del panel con el token de la sesión. */
export async function apiAdmin(ruta, token, opciones = {}) {
  const cabeceras = {
    Accept: 'application/json',
    Authorization: `Bearer ${token}`,
    ...opciones.headers,
  };
  // El tipo de contenido lo decide quien llama: en una subida de foto es
  // multipart, y ahí va el "boundary" que no se puede inventar acá.
  if (opciones.body && !cabeceras['Content-Type']) {
    cabeceras['Content-Type'] = 'application/json';
  }
  return fetch(BASE + '/admin' + ruta, { ...opciones, headers: cabeceras });
}

/** Los datos de una página del panel, o null si la sesión ya no sirve. */
export async function traer(ruta, token) {
  if (!token) return null;
  try {
    const respuesta = await apiAdmin(ruta, token);
    if (!respuesta.ok) return null;
    return await respuesta.json();
  } catch {
    // La API no responde: la página lo muestra como aviso, no se cae.
    return undefined;
  }
}

export async function iniciarSesion(usuario, password) {
  const cuerpo = new URLSearchParams({ username: usuario, password });
  const respuesta = await fetch(BASE + '/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: cuerpo,
  });
  if (!respuesta.ok) return null;
  const datos = await respuesta.json();
  return datos.access_token;
}
