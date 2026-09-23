// Cierra la sesión del panel y vuelve al login. Es un POST desde un form
// normal, así que funciona aunque el JavaScript falle.
import { COOKIE } from '../../lib/admin.js';

export const prerender = false;

export async function POST({ cookies, redirect }) {
  cookies.delete(COOKIE, { path: '/' });
  return redirect('/admin', 303);
}
