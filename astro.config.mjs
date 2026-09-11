// @ts-check
import { defineConfig } from 'astro/config';
import alpinejs from '@astrojs/alpinejs';

export default defineConfig({
  integrations: [alpinejs({ entrypoint: '/src/alpine.js' })],
  site: 'https://elchiconaturista.pe',
});
