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
        setupFiles: ['./vitest.setup.ts'],
        include: ['src/**/*.{test,spec}.{ts,tsx}'],
        css: false,
    },
});
