// Puente entre el navegador y la API del panel.
//
// El token está en una cookie httpOnly, así que el JavaScript de la página no
// puede llamar a FastAPI por su cuenta: manda la petición acá y este endpoint
// la reenvía firmada. Solo reenvía al prefijo /admin de la API, nunca a otra
// ruta.
import { apiAdmin, COOKIE } from '../../../lib/admin.js';

export const prerender = false;

const METODOS = new Set(['GET', 'POST', 'PATCH', 'PUT', 'DELETE']);

async function reenviar({ params, request, cookies, url }) {
  const token = cookies.get(COOKIE)?.value;
  if (!token) {
    return Response.json({ error: 'Sesión no iniciada.' }, { status: 401 });
  }
  if (!METODOS.has(request.method)) {
    return Response.json({ error: 'Método no permitido.' }, { status: 405 });
  }

  // En binario, no como texto: por acá pasan las fotos que se suben.
  const cuerpo = ['GET', 'DELETE'].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  const tipo = request.headers.get('content-type');
  const respuesta = await apiAdmin(`/${params.ruta}${url.search}`, token, {
    method: request.method,
    body: cuerpo,
    headers: tipo ? { 'Content-Type': tipo } : {},
  });

  // Un 204 no lleva cuerpo: construir una Response con uno lanza error.
  if (respuesta.status === 204) return new Response(null, { status: 204 });

  // La descarga de la planilla no es JSON: se reenvía tal cual llega.
  return new Response(await respuesta.arrayBuffer(), {
    status: respuesta.status,
    headers: {
      'Content-Type': respuesta.headers.get('content-type') ?? 'application/json',
      ...(respuesta.headers.get('content-disposition')
        ? { 'Content-Disposition': respuesta.headers.get('content-disposition') }
        : {}),
    },
  });
}

export const GET = reenviar;
export const POST = reenviar;
export const PATCH = reenviar;
export const PUT = reenviar;
export const DELETE = reenviar;
