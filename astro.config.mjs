import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// Pure static output: nginx serves dist/ directly. No SSR runtime, no node process.
export default defineConfig({
  output: 'static',
  site: 'https://satgas.ai.id',
  compressHTML: true,
  build: {
    inlineStylesheets: 'auto',
    assets: '_assets',
  },
  vite: {
    plugins: [tailwindcss()],
    build: {
      cssMinify: 'lightningcss',
    },
  },
});
