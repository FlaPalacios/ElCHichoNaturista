import { ES_DEMO } from '../lib/entorno.js';

// Mientras sea una muestra se cierra el paso a los buscadores. No es solo por
// el SEO: en un plan gratuito el servidor se apaga solo, y cada rastreador que
// pasa lo despierta y gasta las horas del mes.
const DEMO = `User-agent: *
Disallow: /
`;

const ABIERTO = `User-agent: *
Allow: /
Disallow: /admin
Disallow: /api
`;

export function GET() {
  return new Response(ES_DEMO ? DEMO : ABIERTO, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
