import { describe, expect, it, vi } from 'vitest';

// Fonts and global CSS are build-time assets; the test only needs the module.
vi.mock('next/font/google', () => ({ Public_Sans: () => ({ variable: '', className: '' }) }));
vi.mock('@app/assets/css/globals.css', () => ({}));

describe('root layout', () => {
    it('renders every route per request, so runtime flags are never frozen at build time', async () => {
        // SSO_ENABLED and the other runtime flags are read while rendering the
        // root layout. If routes could be prerendered, a build would bake the
        // build machine's value into the image.
        const layout = await import('./layout');
        expect(layout.dynamic).toBe('force-dynamic');
    });
});
