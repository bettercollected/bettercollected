import { afterEach, describe, expect, it, vi } from 'vitest';

import { buildCanonicalFormPath, trackCanonicalFormView } from './umami';

describe('buildCanonicalFormPath', () => {
    it('joins workspace and slug into the shared analytics path', () => {
        expect(buildCanonicalFormPath('acme', 'contact-us')).toBe('/acme/forms/contact-us');
    });
});

describe('trackCanonicalFormView', () => {
    afterEach(() => {
        delete (window as any).umami;
        vi.restoreAllMocks();
    });

    it('does nothing when Umami is not loaded', () => {
        expect(() => trackCanonicalFormView('acme', 'contact-us')).not.toThrow();
    });

    it('does nothing when workspace or slug is missing', () => {
        const track = vi.fn();
        (window as any).umami = { track };

        trackCanonicalFormView('', 'contact-us');
        trackCanonicalFormView('acme', '');

        expect(track).not.toHaveBeenCalled();
    });

    it('tracks a pageview overriding url to the canonical path', () => {
        const track = vi.fn();
        (window as any).umami = { track };

        trackCanonicalFormView('acme', 'contact-us');

        expect(track).toHaveBeenCalledTimes(1);
        const callback = track.mock.calls[0][0];
        expect(callback({ url: '/forms/contact-us', title: 'x' })).toEqual({
            url: '/acme/forms/contact-us',
            title: 'x'
        });
    });

    it('fails silently if umami.track throws', () => {
        (window as any).umami = {
            track: () => {
                throw new Error('boom');
            }
        };

        expect(() => trackCanonicalFormView('acme', 'contact-us')).not.toThrow();
    });
});
