// Entrada y salida del panel. Guarda el token en una cookie httpOnly.
import { COOKIE, iniciarSesion, opcionesCookie } from '../../../lib/admin.js';

export const prerender = false;

export async function POST({ request, cookies }) {
  const { usuario, password } = await request.json();
  const token = await iniciarSesion(usuario ?? '', password ?? '');

  if (!token) {
    return Response.json(
      { error: 'Usuario o contraseña incorrectos.' },
      { status: 401 }
    );
  }

  cookies.set(COOKIE, token, opcionesCookie);
  return Response.json({ ok: true });
}

export async function DELETE({ cookies }) {
  cookies.delete(COOKIE, { path: '/' });
  return Response.json({ ok: true });
}
