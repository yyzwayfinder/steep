import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: false },
      '/healthz': 'http://localhost:8000',
    },
  },
  build: { outDir: 'dist', assetsDir: 'assets', sourcemap: false, assetsInlineLimit: 0 },
});
