// @ts-check
import { defineConfig } from 'astro/config';
import alpinejs from '@astrojs/alpinejs';
import node from '@astrojs/node';

// SSR: cada visita consulta la API, así los cambios de precio y stock que se
// hagan desde el panel se ven de inmediato, sin recompilar el sitio.
export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  integrations: [alpinejs({ entrypoint: '/src/alpine.js' })],
  site: 'https://elchiconaturista.pe',
});
