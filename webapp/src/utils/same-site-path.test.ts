import { describe, expect, it } from 'vitest';

import { SERVER_PATH_ORIGIN, isSameSitePath } from './same-site-path';

describe('isSameSitePath', () => {
    it('takes only a path of this origin', () => {
        expect(isSameSitePath('/acme/dashboard/deletion-requests')).toBe(true);
        expect(isSameSitePath('/acme/dashboard/forms?page=2')).toBe(true);
        expect(isSameSitePath('/\\evil.example.com')).toBe(false);
        expect(isSameSitePath(undefined)).toBe(false);
        expect(isSameSitePath(42)).toBe(false);
    });

    it.each(['//evil.example.com', '/\\evil.example.com', '\\\\evil.example.com', 'https://evil.example.com/x', 'javascript:alert(1)', '/acme\\..\\x', '/\t/evil.example.com', '/\n/evil.example.com', 'acme/dashboard', ''])(
        'never takes an address that is not a path of this site: %j',
        (address) => {
            expect(isSameSitePath(address)).toBe(false);
            expect(isSameSitePath(address, SERVER_PATH_ORIGIN)).toBe(false);
        }
    );

    it('works on the server against a fixed origin', () => {
        expect(isSameSitePath('/acme/dashboard/forms/f1/responses', SERVER_PATH_ORIGIN)).toBe(true);
    });
});
