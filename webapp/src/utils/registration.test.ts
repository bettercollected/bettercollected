import { describe, expect, it } from 'vitest';

import {
    DELIVERY_ERROR_CODES,
    ERROR_CODES,
    TEST_CODES,
    VARIABLE_REASONS,
    canBeList,
    defaultKeyOf,
    deliveryErrorKey,
    errorCodeOf,
    errorKey,
    formErrorField,
    isValidKey,
    needsSecretAgain,
    serviceErrorField,
    testKey,
    variableReasonKey
} from '@app/utils/registration';

import enBuilder from '../../public/locales/en/builder.json';
import nlBuilder from '../../public/locales/nl/builder.json';

const resolve = (tree: any, key: string) => key.split('.').reduce((node, part) => node?.[part], tree);
const leaves = (tree: any, prefix = ''): string[] => Object.entries(tree).flatMap(([k, v]) => (typeof v === 'object' && v !== null ? leaves(v, `${prefix}${k}.`) : [`${prefix}${k}`]));

describe('registration error codes', () => {
    it.each(ERROR_CODES)('maps the refusal "%s" to a sentence in English and Dutch', (code) => {
        const key = errorKey(code);
        expect(key).toBe(`REGISTRATION.ERROR.${code}`);
        expect(resolve(enBuilder, key)).toEqual(expect.any(String));
        expect(resolve(nlBuilder, key)).toEqual(expect.any(String));
    });

    it.each(TEST_CODES)('maps the test outcome "%s"', (code) => {
        expect(resolve(enBuilder, testKey(false, code))).toEqual(expect.any(String));
        expect(resolve(nlBuilder, testKey(false, code))).toEqual(expect.any(String));
    });

    it.each(DELIVERY_ERROR_CODES)('maps the delivery reason "%s"', (code) => {
        expect(resolve(enBuilder, deliveryErrorKey(code))).toEqual(expect.any(String));
        expect(resolve(nlBuilder, deliveryErrorKey(code))).toEqual(expect.any(String));
    });

    it.each(VARIABLE_REASONS)('maps the variable reason "%s"', (reason) => {
        expect(resolve(enBuilder, variableReasonKey(reason))).toEqual(expect.any(String));
        expect(resolve(nlBuilder, variableReasonKey(reason))).toEqual(expect.any(String));
    });

    it('falls back to a generic sentence for a code it does not know, and never to the API text', () => {
        expect(errorKey('something_new')).toBe('REGISTRATION.ERROR.unknown');
        expect(errorKey(undefined)).toBe('REGISTRATION.ERROR.unknown');
        expect(testKey(false, 'something_new')).toBe('REGISTRATION.TEST.unknown');
        expect(testKey(true)).toBe('REGISTRATION.TEST.ok');
        expect(deliveryErrorKey(null)).toBe('REGISTRATION.DELIVERY.ERROR.unknown');
        expect(deliveryErrorKey('<img src=x onerror=alert(1)>')).toBe('REGISTRATION.DELIVERY.ERROR.unknown');
    });

    it('reads the code from the body, else from the status', () => {
        expect(errorCodeOf({ status: 422, data: { code: 'invalid_url', message: 'x' } })).toBe('invalid_url');
        expect(errorCodeOf({ status: 410, data: { code: 'registration_off' } })).toBe('registration_off');
        expect(errorCodeOf({ status: 403, data: { detail: 'nope' } })).toBe('forbidden');
        expect(errorCodeOf({ status: 404 })).toBe('not_found');
        expect(errorCodeOf({ status: 410 })).toBe('registration_off');
        expect(errorCodeOf({ status: 500, data: 'oops' })).toBe('unknown');
        expect(errorCodeOf(undefined)).toBe('unknown');
    });

    it('puts a refusal next to the field it is about', () => {
        expect(serviceErrorField('invalid_url')).toBe('baseUrl');
        expect(serviceErrorField('not_allowed')).toBe('baseUrl');
        expect(serviceErrorField('secret_required')).toBe('secret');
        expect(serviceErrorField('name_taken')).toBe('name');
        expect(serviceErrorField('invalid_auth_name')).toBe('authName');
        expect(serviceErrorField('service_in_use')).toBeNull();
        expect(formErrorField('service_required')).toBe('service');
        expect(formErrorField('invalid_path')).toBe('path');
        expect(formErrorField('invalid_key')).toBe('variables');
        expect(formErrorField('form_not_collected_here')).toBeNull();
    });
});

describe('registration copy', () => {
    it('has the same keys in English and Dutch', () => {
        // Dutch has no plural suffix beyond _one/_other, same as English.
        expect(leaves(nlBuilder.REGISTRATION).sort()).toEqual(leaves(enBuilder.REGISTRATION).sort());
    });

    it('is plain: no sentence runs past 28 words, and the copy names no public body', () => {
        for (const [lang, tree] of [
            ['en', enBuilder.REGISTRATION],
            ['nl', nlBuilder.REGISTRATION]
        ] as const) {
            for (const key of leaves(tree)) {
                const text = resolve(tree, key) as string;
                const longest = Math.max(...text.split(/(?<=[.!?])\s+/).map((sentence) => sentence.split(/\s+/).length));
                expect(longest, `${lang} ${key}`).toBeLessThanOrEqual(28);
                expect(text, `${lang} ${key}`).not.toMatch(/gemeente|overheid|municipal|government/i);
            }
        }
    });
});

describe('keys and secrets', () => {
    it('turns a source into the default name the API would use', () => {
        expect(defaultKeyOf('field-1.a b')).toBe('field_1_a_b');
        expect(isValidKey('postcode')).toBe(true);
        expect(isValidKey('_x1')).toBe(true);
        expect(isValidKey('1abc')).toBe(false);
        expect(isValidKey('a-b')).toBe(false);
        expect(isValidKey('a'.repeat(65))).toBe(false);
        // a default that starts with a digit has to be named by hand
        expect(isValidKey(defaultKeyOf('9f3a'))).toBe(false);
    });

    const service: any = { baseUrl: 'https://cases.example.org', auth: 'header', authName: 'X-Api-Key' };
    it('asks for the secret again only when the address or the sign-in changed', () => {
        expect(needsSecretAgain(service, { baseUrl: 'https://cases.example.org', auth: 'header', authName: 'X-Api-Key' })).toBe(false);
        expect(needsSecretAgain(service, { baseUrl: 'https://other.example.org', auth: 'header', authName: 'X-Api-Key' })).toBe(true);
        expect(needsSecretAgain(service, { baseUrl: 'https://cases.example.org', auth: 'basic', authName: 'X-Api-Key' })).toBe(true);
        expect(needsSecretAgain(service, { baseUrl: 'https://cases.example.org', auth: 'header', authName: 'Authorization' })).toBe(true);
        expect(needsSecretAgain(service, { baseUrl: 'https://other.example.org', auth: 'none', authName: '' })).toBe(false);
    });

    it('offers "send as list" for multiple choice only', () => {
        expect(canBeList({ source: 'a', label: 'A', type: 'multiple_choice', supported: true })).toBe(true);
        expect(canBeList({ source: 'a', label: 'A', type: 'short_text', supported: true })).toBe(false);
    });
});
