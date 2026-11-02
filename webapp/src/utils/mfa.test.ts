import { describe, expect, it } from 'vitest';

import { isMfaRequired, mfaFailureOf, normaliseCode, safeNextPath, waitMinutes } from './mfa';

describe('mfaFailureOf', () => {
    it('reads the status, the code and the wait of a refusal', () => {
        expect(mfaFailureOf({ status: 429, data: { code: 'mfa_locked', retry_after: 840 } })).toEqual({ status: 429, code: 'mfa_locked', retryAfter: 840 });
    });

    it('never throws on anything else', () => {
        expect(mfaFailureOf(undefined)).toEqual({ status: undefined, code: undefined, retryAfter: undefined });
        expect(mfaFailureOf({ status: 'FETCH_ERROR', error: 'x' })).toEqual({ status: undefined, code: undefined, retryAfter: undefined });
        expect(mfaFailureOf({ status: 500, data: 'plain text' })).toMatchObject({ status: 500, code: undefined });
        expect(mfaFailureOf({ status: 429, data: { retry_after: 'soon' } }).retryAfter).toBeUndefined();
    });
});

describe('waitMinutes', () => {
    it('rounds up to whole minutes, at least one, and assumes the lock time when unknown', () => {
        expect(waitMinutes(1)).toBe(1);
        expect(waitMinutes(61)).toBe(2);
        expect(waitMinutes(900)).toBe(15);
        expect(waitMinutes(undefined)).toBe(15);
    });
});

describe('normaliseCode', () => {
    it('removes the spaces of a six-digit code', () => {
        expect(normaliseCode(' 123 456 ', false)).toBe('123456');
    });

    it('upper-cases a recovery code and keeps its dashes', () => {
        expect(normaliseCode('abcd-efgh-ijkl-mnop ', true)).toBe('ABCD-EFGH-IJKL-MNOP');
    });
});

describe('isMfaRequired', () => {
    it('is true only for the server answer that asks for the second step', () => {
        expect(isMfaRequired({ mfaRequired: true })).toBe(true);
        expect(isMfaRequired({ mfaRequired: 'yes' })).toBe(false);
        expect(isMfaRequired({ access_token: 'x' })).toBe(false);
        expect(isMfaRequired(undefined)).toBe(false);
    });
});

describe('safeNextPath', () => {
    const origin = 'https://admin.example.test';

    it('follows a path of this site', () => {
        expect(safeNextPath('/acme/dashboard/forms?x=1', origin)).toBe('/acme/dashboard/forms?x=1');
    });

    it('turns an address of this origin into its path', () => {
        expect(safeNextPath('https://admin.example.test/acme/dashboard#top', origin)).toBe('/acme/dashboard#top');
    });

    it.each(['https://evil.example/', '//evil.example/x', '/\\evil.example', 'javascript:alert(1)', '/\t/evil.example', '%2F%2Fevil.com', '/%5Cevil.com', '/%5cevil.com', '/%2F/evil.com', '/\\evil.com', '//evil.com', 'https:evil.com', '', undefined, null])('never follows %j', (value) => {
        expect(safeNextPath(value as string | undefined, origin)).toBeUndefined();
    });
});
