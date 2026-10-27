import { describe, expect, it } from 'vitest';

import {
    CHECK_CODES,
    DEFAULT_REFERENCE_PATH,
    DELIVERY_ERROR_CODES,
    ERROR_CODES,
    TEST_CODES,
    VARIABLE_REASONS,
    canBeList,
    checkKey,
    defaultKeyOf,
    deliveryErrorKey,
    errorCodeOf,
    errorKey,
    findTargetConflict,
    formErrorField,
    formatTargetPath,
    isPlainToken,
    isValidKey,
    isValidObjectTypeVersion,
    isValidSegment,
    needsSecretAgain,
    objectTypeUrlProblem,
    parseTargetPath,
    referenceConflicts,
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

describe('Objects API: check outcomes and delivery codes', () => {
    it.each(CHECK_CODES)('maps the connection check outcome "%s" in English and Dutch', (code) => {
        expect(checkKey(false, code)).toBe(`REGISTRATION.CHECK.${code}`);
        expect(resolve(enBuilder, checkKey(false, code))).toEqual(expect.any(String));
        expect(resolve(nlBuilder, checkKey(false, code))).toEqual(expect.any(String));
    });

    it('has a sentence for ok and for a code it does not know', () => {
        expect(checkKey(true)).toBe('REGISTRATION.CHECK.ok');
        expect(checkKey(false, 'something_new')).toBe('REGISTRATION.CHECK.unknown');
        expect(checkKey(false, null)).toBe('REGISTRATION.CHECK.unknown');
    });

    it('reads a 429 as rate_limited, with or without a body', () => {
        expect(errorCodeOf({ status: 429, data: { code: 'rate_limited' } })).toBe('rate_limited');
        expect(errorCodeOf({ status: 429 })).toBe('rate_limited');
    });

    it('words lookup_failed, and an Objects API 400 as a schema mismatch only for that kind', () => {
        expect(DELIVERY_ERROR_CODES).toContain('lookup_failed');
        expect(deliveryErrorKey('lookup_failed')).toBe('REGISTRATION.DELIVERY.ERROR.lookup_failed');
        expect(deliveryErrorKey('http_4xx', { objectsApi: true, httpStatus: 400 })).toBe('REGISTRATION.DELIVERY.ERROR.http_4xx_schema');
        expect(deliveryErrorKey('http_4xx', { objectsApi: true, httpStatus: 403 })).toBe('REGISTRATION.DELIVERY.ERROR.http_4xx_token');
        expect(deliveryErrorKey('http_4xx', { objectsApi: true, httpStatus: 404 })).toBe('REGISTRATION.DELIVERY.ERROR.http_4xx');
        expect(resolve(nlBuilder, 'REGISTRATION.DELIVERY.ERROR.http_4xx_token')).toEqual(expect.any(String));
        expect(deliveryErrorKey('http_4xx', { objectsApi: false, httpStatus: 400 })).toBe('REGISTRATION.DELIVERY.ERROR.http_4xx');
        expect(resolve(enBuilder, 'REGISTRATION.DELIVERY.ERROR.http_4xx_schema')).toEqual(expect.any(String));
    });

    it('puts the Objects API refusals next to their field, and the unclear addresses nowhere', () => {
        expect(serviceErrorField('objecttypes_base_required')).toBe('objecttypesBaseUrl');
        expect(serviceErrorField('invalid_url', 'objects_api')).toBeNull();
        expect(serviceErrorField('invalid_url', 'generic_json')).toBe('baseUrl');
        expect(formErrorField('invalid_object_type_url')).toBe('objectType');
        expect(formErrorField('object_type_outside_base')).toBe('objectType');
        expect(formErrorField('invalid_object_type_version')).toBe('version');
        expect(formErrorField('invalid_reference_path')).toBe('reference');
        expect(formErrorField('reference_path_conflict')).toBe('reference');
        expect(formErrorField('target_path_conflict')).toBe('variables');
        expect(formErrorField('not_an_objects_api')).toBe('service');
    });
});

describe('Objects API: object type address', () => {
    const base = 'https://objecttypes.example.org/api/v2/';
    const id = '0f9a3b1c-5d2e-4f6a-8b7c-1d2e3f4a5b6c';
    const ok = `https://objecttypes.example.org/api/v2/objecttypes/${id}`;

    it('accepts an address under the base', () => {
        expect(objectTypeUrlProblem(ok, base)).toBeNull();
        expect(objectTypeUrlProblem(ok.replace('objecttypes.example.org', 'ObjectTypes.Example.ORG'), base)).toBeNull();
        expect(objectTypeUrlProblem(ok)).toBeNull();
    });

    it.each([
        ['http instead of https', ok.replace('https', 'http')],
        ['a user name', ok.replace('https://', 'https://user@')],
        ['a port', ok.replace('.org', '.org:8443')],
        ['a query', `${ok}?x=1`],
        ['a fragment', `${ok}#x`],
        ['a trailing slash', `${ok}/`],
        ['no uuid', 'https://objecttypes.example.org/api/v2/objecttypes/abc'],
        ['another last segment', `https://objecttypes.example.org/api/v2/objects/${id}`],
        ['a dot segment', `https://objecttypes.example.org/api/v2/../v2/objecttypes/${id}`],
        ['a percent sign', `https://objecttypes.example.org/api/%2e%2e/objecttypes/${id}`],
        ['a semicolon', `https://objecttypes.example.org/api;x/objecttypes/${id}`],
        ['an empty segment', `https://objecttypes.example.org/api//objecttypes/${id}`],
        ['a space', `${ok} x`],
        ['more than 1000 characters', `https://objecttypes.example.org/${'a/'.repeat(500)}objecttypes/${id}`],
        ['nothing', '']
    ])('refuses %s', (_label, value) => {
        expect(objectTypeUrlProblem(value, base)).toBe('invalid_object_type_url');
    });

    it('refuses an address outside the service base: other host, look-alike host, other path, user-info trick', () => {
        expect(objectTypeUrlProblem(`https://other.example.org/api/v2/objecttypes/${id}`, base)).toBe('object_type_outside_base');
        expect(objectTypeUrlProblem(`https://objecttypes.example.org.evil.test/api/v2/objecttypes/${id}`, base)).toBe('object_type_outside_base');
        expect(objectTypeUrlProblem(`https://objecttypes.example.org/api/v3/objecttypes/${id}`, base)).toBe('object_type_outside_base');
        expect(objectTypeUrlProblem(`https://objecttypes.example.org/api/v2x/objecttypes/${id}`, base)).toBe('object_type_outside_base');
        expect(objectTypeUrlProblem(`https://objecttypes.example.org@evil.test/api/v2/objecttypes/${id}`, base)).toBe('invalid_object_type_url');
    });

    it('takes a version from 1 to 10000', () => {
        expect(['1', '10', '10000', ' 7 '].every(isValidObjectTypeVersion)).toBe(true);
        expect(['', '0', '10001', '-1', '1.5', 'abc', '1e3', '000001'.padEnd(6, '1')].some(isValidObjectTypeVersion)).toBe(false);
    });
});

describe('Objects API: target paths and the reference path', () => {
    it('parses a.b.c into segments and back', () => {
        expect(parseTargetPath('a.b.c')).toEqual(['a', 'b', 'c']);
        expect(parseTargetPath(' applicant . postcode ')).toEqual(['applicant', 'postcode']);
        expect(formatTargetPath(['a', 'b'])).toBe('a.b');
        expect(formatTargetPath(null)).toBe('');
        expect(DEFAULT_REFERENCE_PATH).toBe('bettercollected_reference');
        expect(parseTargetPath(DEFAULT_REFERENCE_PATH)).toEqual([DEFAULT_REFERENCE_PATH]);
    });

    it.each(['', '.', 'a..b', 'a.', '.a', '1a', 'a-b', 'a__b', 'a_', 'a.b_', '_a', 'a b', 'a'.repeat(65), 'a.b.c.d.e.f.g.h.i'])('refuses "%s"', (text) => {
        expect(parseTargetPath(text)).toBeNull();
    });

    it('allows 8 levels and 64 characters', () => {
        expect(parseTargetPath('a.b.c.d.e.f.g.h')).toHaveLength(8);
        expect(isValidSegment('a'.repeat(64))).toBe(true);
        expect(isValidSegment('a'.repeat(65))).toBe(false);
    });

    it('finds two paths that are the same or one inside the other', () => {
        const paths = (...list: string[]) => list.map((text, index) => ({ source: `q${index}`, path: parseTargetPath(text)! }));
        expect(findTargetConflict(paths('a.b', 'a.c', 'd'))).toBeNull();
        expect(findTargetConflict(paths('a.b', 'a.b'))).toEqual({ first: 'q0', second: 'q1' });
        expect(findTargetConflict(paths('a', 'x', 'a.b'))).toEqual({ first: 'q0', second: 'q2' });
        expect(findTargetConflict(paths('a.b.c', 'a.b'))).toEqual({ first: 'q0', second: 'q1' });
    });

    it('keeps the reference path apart from the mapped ones', () => {
        const mapped = [['applicant', 'postcode'], ['city']];
        expect(referenceConflicts(['bettercollected_reference'], mapped)).toBe(false);
        expect(referenceConflicts(['applicant'], mapped)).toBe(true);
        expect(referenceConflicts(['applicant', 'postcode', 'x'], mapped)).toBe(true);
        expect(referenceConflicts(['city'], mapped)).toBe(true);
    });

    it('takes a token without whitespace or non-ASCII', () => {
        expect(isPlainToken('abc123DEF')).toBe(true);
        expect(['', 'a b', 'a\tb', 'tökén', ' abc'].some(isPlainToken)).toBe(false);
    });

    it('asks for the token again when the Objects API address changes, but not the object types address', () => {
        const objects: any = { kind: 'objects_api', baseUrl: 'https://objects.example.org/api/v2/', objecttypesBaseUrl: 'https://types.example.org/api/v2/', auth: 'token' };
        expect(needsSecretAgain(objects, { baseUrl: 'https://objects.example.org/api/v2/', auth: 'token', authName: '' })).toBe(false);
        expect(needsSecretAgain(objects, { baseUrl: 'https://other.example.org/api/v2/', auth: 'token', authName: '' })).toBe(true);
    });
});
