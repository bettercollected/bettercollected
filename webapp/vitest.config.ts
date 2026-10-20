import { resolve } from 'path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Frontend unit-test runner. Kept separate from the Next.js build: test files
// are excluded from tsconfig (see tsconfig.json) so `next build` never tries to
// type-check them. Path aliases mirror tsconfig `paths`.
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@app': resolve(__dirname, './src'),
            '@Components': resolve(__dirname, './src/components'),
        },
    },
    test: {
        globals: true,
        environment: 'jsdom',
        // One jsdom per worker, each test file in its own VM context (still
        // isolated). The default pool built jsdom once per file: 162 times,
        // a third of the run's time.
        pool: 'vmThreads',
        deps: {
            optimizer: {
                // html-react-parser is CommonJS that requires an ES module
                // (domhandler); Node 22 cannot load that inside a VM context.
                // Pre-bundled by Vite it is one ES module.
                client: { enabled: true, include: ['html-react-parser'] }
            }
        },
        setupFiles: ['./vitest.setup.ts'],
        include: ['src/**/*.{test,spec}.{ts,tsx}'],
        css: false,
    },
});
