import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react()],
    server: {
      port: 5173, strictPort: true,
      proxy: { '/graphql': { target: env.GATEWAY_PROXY_TARGET || 'http://localhost:5000', changeOrigin: true } },
    },
  };
});
