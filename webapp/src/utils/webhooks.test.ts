import { describe, expect, it } from 'vitest';

import enBuilder from '../../public/locales/en/builder.json';
import nlBuilder from '../../public/locales/nl/builder.json';
import { DELIVERY_ERROR_CODES, ERROR_CODES, defaultKeyOf, deliveryErrorKey, errorCodeOf, errorField, errorKey, formatDuration, isValidKey, urlProblem } from './webhooks';

describe('urlProblem', () => {
    it.each([
        ['https://hooks.example.org/in', null],
        ['https://hooks.example.org', null],
        ['  https://hooks.example.org/in?token=abc  ', null],
        ['https://hooks.example.org:443/in', null],
        ['https://bücher.example/hook', null]
    ])('accepts %s', (value, expected) => {
        expect(urlProblem(value)).toBe(expected);
    });

    it.each([
        ['', 'empty'],
        ['   ', 'empty'],
        ['http://hooks.example.org/in', 'not_https'],
        ['hooks.example.org/in', 'not_https'],
        ['ftp://hooks.example.org', 'not_https'],
        ['https://user:pw@hooks.example.org/in', 'invalid_url'],
        ['https://hooks.example.org@evil.example/in', 'invalid_url'],
        ['https://hooks.example.org:8443/in', 'invalid_url'],
        ['https://127.0.0.1/in', 'invalid_url'],
        ['https://2130706433/in', 'invalid_url'],
        ['https://[::1]/in', 'invalid_url'],
        ['https://localhost/in', 'invalid_url'],
        ['https://hooks.example.org/a b', 'invalid_url'],
        ['https://hooks.example.org\\in', 'invalid_url'],
        ['https://' + 'a'.repeat(2100) + '.example.org', 'invalid_url']
    ])('refuses %s', (value, expected) => {
        expect(urlProblem(value)).toBe(expected);
    });
});

describe('names, codes and keys', () => {
    it('keeps names to what the server accepts', () => {
        expect(isValidKey('full_name')).toBe(true);
        expect(isValidKey('_x1')).toBe(true);
        for (const bad of ['', '1x', 'a b', 'é', 'a'.repeat(65), 'a-b']) expect(isValidKey(bad)).toBe(false);
        expect(defaultKeyOf('people.name')).toBe('people_name');
    });

    it('reads the code of a failed call from the API, else from the status', () => {
        expect(errorCodeOf({ data: { code: 'not_allowed' } })).toBe('not_allowed');
        expect(errorCodeOf({ status: 403 })).toBe('forbidden');
        expect(errorCodeOf({ status: 404 })).toBe('not_found');
        expect(errorCodeOf({ status: 429 })).toBe('rate_limited');
        expect(errorCodeOf({ status: 500 })).toBe('unknown');
        expect(errorCodeOf(undefined)).toBe('unknown');
    });

    it('puts a refusal next to the field it belongs to', () => {
        for (const code of ['invalid_url', 'not_https', 'not_allowed', 'unreachable']) expect(errorField(code)).toBe('url');
        for (const code of ['invalid_key', 'file_not_sent', 'unknown_variable']) expect(errorField(code)).toBe('fields');
        expect(errorField('webhooks_off')).toBeNull();
    });

    it('has a sentence in English and Dutch for every code, and a fallback', () => {
        for (const tree of [enBuilder.WEBHOOKS as any, nlBuilder.WEBHOOKS as any]) {
            for (const code of ERROR_CODES) expect(tree.ERROR[code], code).toBeTruthy();
            for (const code of DELIVERY_ERROR_CODES) expect(tree.DELIVERIES.ERROR[code], code).toBeTruthy();
            expect(tree.ERROR.unknown).toBeTruthy();
            expect(tree.DELIVERIES.ERROR.unknown).toBeTruthy();
        }
        expect(errorKey('not_allowed')).toBe('WEBHOOKS.ERROR.not_allowed');
        expect(errorKey('something_new')).toBe('WEBHOOKS.ERROR.unknown');
        expect(deliveryErrorKey('timeout')).toBe('WEBHOOKS.DELIVERIES.ERROR.timeout');
        expect(deliveryErrorKey(null)).toBe('WEBHOOKS.DELIVERIES.ERROR.unknown');
    });

    it('formats timings', () => {
        expect(formatDuration(850)).toBe('850 ms');
        expect(formatDuration(2400)).toBe('2.4 s');
        expect(formatDuration(null)).toBe('');
    });
});
