import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export function resolveGatewayUrl(): string {
  if (process.env.VITE_GATEWAY_URL) {
    return process.env.VITE_GATEWAY_URL;
  }
  if (process.env.GATEWAY_URL) {
    return process.env.GATEWAY_URL;
  }
  const projectNumber = process.env.GOOGLE_CLOUD_PROJECT_NUMBER || process.env.PROJECT_NUMBER;
  const region = process.env.GOOGLE_CLOUD_REGION || process.env.REGION;
  if (projectNumber && region) {
    return `https://portfolio-copilot-gateway-${projectNumber}.${region}.run.app`;
  }
  return 'http://localhost:8080';
}

const gatewayTarget = resolveGatewayUrl();

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: gatewayTarget,
        changeOrigin: true,
        secure: false
      },
      '/health': {
        target: gatewayTarget,
        changeOrigin: true,
        secure: false
      }
    }
  }
});
