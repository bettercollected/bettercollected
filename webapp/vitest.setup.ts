// Extends Vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.)
// and clears the rendered DOM between tests.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// next/font is resolved by the Next.js compiler at build time.
vi.mock('@app/assets/fonts/leaflet-serif', () => ({ leafletSerif: { className: '', variable: '', style: { fontFamily: "'Source Serif 4'" } } }));
vi.mock('@app/assets/fonts/theme-faces', () => ({
    themeFaces: {
        'atkinson-next': "'Atkinson Hyperlegible Next', ui-sans-serif, system-ui, sans-serif",
        archivo: "'Archivo', ui-sans-serif, system-ui, sans-serif",
        besley: "'Besley', Georgia, 'Times New Roman', serif",
        rubik: "'Rubik', ui-sans-serif, system-ui, sans-serif",
        'atkinson-mono': "'Atkinson Hyperlegible Mono', ui-monospace, monospace"
    }
}));

afterEach(() => {
    cleanup();
});
