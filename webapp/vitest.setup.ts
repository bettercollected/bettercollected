// Extends Vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.)
// and clears the rendered DOM between tests.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// next/font is resolved by the Next.js compiler at build time.
vi.mock('@app/assets/fonts/leaflet-serif', () => ({ leafletSerif: { className: '', variable: '', style: { fontFamily: "'Source Serif 4'" } } }));

afterEach(() => {
    cleanup();
});
