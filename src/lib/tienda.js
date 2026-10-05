// Los datos de la tienda salen de la API, que los sirve desde la base para
// que Fernando pueda cambiarlos desde el panel. Si la API no responde se usan
// los de `src/data/tienda.js`, y el sitio sigue mostrando algo sensato.

import { tienda as respaldo } from '../data/tienda.js';
import { ESPERA } from './entorno.js';

const BASE = (
  import.meta.env.PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '');

export async function cargarTienda() {
  try {
    const respuesta = await fetch(BASE + '/tienda', {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(ESPERA),
    });
    if (!respuesta.ok) return respaldo;
    const d = await respuesta.json();
    return {
      nombre: d.nombre,
      lema: d.lema,
      whatsapp: d.whatsapp,
      whatsappVisible: d.whatsapp_visible,
      correo: d.correo,
      direccion: d.direccion,
      horario: d.horario,
      tiktok: d.tiktok,
      linkedin: d.linkedin,
      metodosPago: d.metodos_pago,
      plantillaWhatsapp: d.plantilla_whatsapp,
      avisos: d.avisos,
      mostrarAgotado: Boolean(d.mostrar_agotado),
      envioGratisDesde: Number(d.envio_gratis_desde),
    };
  } catch {
    return respaldo;
  }
}

/** Arma el enlace wa.me con un mensaje ya escrito. */
export const waLink = (tienda, mensaje) =>
  `https://wa.me/${tienda.whatsapp}?text=${encodeURIComponent(mensaje)}`;
