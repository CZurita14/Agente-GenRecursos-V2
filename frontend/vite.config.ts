import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// En desarrollo el navegador ve un solo origen (localhost:5173): /api/* se reenvía a la
// API del P4. Así la cookie de sesión (HttpOnly, SameSite=Lax) y el Origin exacto funcionan.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        rewrite: ruta => ruta.replace(/^\/api/, ''),
      },
    },
  },
});
