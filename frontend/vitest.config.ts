import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  // Read the immutable Gateway contract only in the Node test runner, never through Vite's dev server.
  define: { __CHAT_CONTRACT__: JSON.stringify(readFileSync(new URL('../gateway/tests/contract_v1.graphql', import.meta.url), 'utf8')) },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'] },
});
