/**
 * The assertion verifier must match the service's algorithm exactly
 * (docs/edge-routing.md): tokens are built here the way the edge builds them.
 */
import { createHmac } from 'node:crypto';
import { describe, expect, it } from 'vitest';

import { AssertionInvalid, decideAssertion, parseAssertionKeys, verifyAssertion } from '@app/lib/server/custom-domain';

const KEYS = { '1': 'a-very-long-secret-for-key-one-0123456789', '2': 'previous-key-secret-abcdefghijklmnopqrstu' };
const NOW = 1_800_000_000;

function token(payload: Record<string, unknown>, keyId = '1', secret: string = KEYS[keyId as '1' | '2']) {
    const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
    const mac = createHmac('sha256', secret).update(`v1.${keyId}.${body}`).digest('base64url');
    return `v1.${keyId}.${body}.${mac}`;
}

const payload = { app: 'app-1', dom: 'dom-1', ref: '64ae38bcdea80b08417d058a', host: 'forms.customer.example', iat: NOW - 5, exp: NOW + 55, rid: 'req-1' };
const options = { applicationId: 'app-1', hostname: 'forms.customer.example', now: NOW };

function code(fn: () => unknown) {
    try {
        fn();
    } catch (error) {
        return error instanceof AssertionInvalid ? error.code : 'other';
    }
    return 'ok';
}

describe('verifyAssertion', () => {
    it('accepts a token signed with any configured key', () => {
        const assertion = verifyAssertion(token(payload), KEYS, options);
        expect(assertion.reference).toBe(payload.ref);
        expect(assertion.hostname).toBe('forms.customer.example');
        expect(verifyAssertion(token(payload, '2'), KEYS, options).keyId).toBe('2');
    });

    it('ignores the port and case of the request host', () => {
        expect(verifyAssertion(token(payload), KEYS, { ...options, hostname: 'Forms.Customer.Example:443' }).domainId).toBe('dom-1');
    });

    it('rejects every way a token can be wrong, with a stable code', () => {
        expect(code(() => verifyAssertion(null, KEYS, options))).toBe('missing');
        expect(code(() => verifyAssertion('v2.1.x.y', KEYS, options))).toBe('malformed');
        expect(code(() => verifyAssertion(token(payload, '9', 'unknown'), KEYS, options))).toBe('unknown_key');
        expect(code(() => verifyAssertion(token(payload, '1', 'forged-secret'), KEYS, options))).toBe('bad_signature');
        expect(code(() => verifyAssertion(token({ ...payload, exp: NOW - 60 }), KEYS, options))).toBe('expired');
        expect(code(() => verifyAssertion(token({ ...payload, iat: NOW + 120 }), KEYS, options))).toBe('not_yet_valid');
        expect(code(() => verifyAssertion(token({ ...payload, app: 'other-app' }), KEYS, options))).toBe('wrong_application');
        expect(code(() => verifyAssertion(token(payload), KEYS, { ...options, hostname: 'other.example' }))).toBe('wrong_hostname');
        expect(code(() => verifyAssertion(token({ app: 'app-1' }), KEYS, options))).toBe('malformed');
    });

    it("accepts the hosted service's per-application key ids (app_…)", () => {
        const hostedKeys = parseAssertionKeys('app_2f9c1a:hosted-application-secret-0123456789abcdef');
        const signed = token(payload, 'app_2f9c1a', hostedKeys['app_2f9c1a']);
        expect(verifyAssertion(signed, hostedKeys, options).keyId).toBe('app_2f9c1a');
        // another application's key on the shared edge is not in our keyring
        expect(code(() => verifyAssertion(token(payload, 'app_other', 'another-applications-secret-0123456789'), hostedKeys, options))).toBe('unknown_key');
        // our key but naming another application
        expect(code(() => verifyAssertion(token({ ...payload, app: 'other-app' }, 'app_2f9c1a', hostedKeys['app_2f9c1a']), hostedKeys, options))).toBe('wrong_application');
    });

    it('tolerates clock skew of 30 seconds', () => {
        expect(code(() => verifyAssertion(token({ ...payload, exp: NOW - 20 }), KEYS, options))).toBe('ok');
        expect(code(() => verifyAssertion(token({ ...payload, exp: NOW - 40 }), KEYS, options))).toBe('expired');
    });
});

describe('decideAssertion', () => {
    const config = { keys: KEYS, applicationId: 'app-1' };
    it('required: a missing assertion is refused', () => {
        expect(decideAssertion(null, { ...config, mode: 'required' }, 'forms.customer.example', NOW)).toEqual({ kind: 'refused', error: 'missing' });
    });
    it('optional: a missing assertion falls back to the legacy host lookup, an invalid one is still refused', () => {
        expect(decideAssertion(null, { ...config, mode: 'optional' }, 'forms.customer.example', NOW)).toEqual({ kind: 'legacy' });
        expect(decideAssertion(token(payload, '1', 'forged'), { ...config, mode: 'optional' }, 'forms.customer.example', NOW)).toEqual({ kind: 'refused', error: 'bad_signature' });
        expect(decideAssertion(token({ ...payload, exp: NOW - 100 }), { ...config, mode: 'optional' }, 'forms.customer.example', NOW)).toEqual({ kind: 'refused', error: 'expired' });
    });
    it('a valid assertion selects the workspace in both modes', () => {
        for (const mode of ['optional', 'required'] as const) {
            const decision = decideAssertion(token(payload), { ...config, mode }, 'forms.customer.example', NOW);
            expect(decision.kind).toBe('assertion');
            if (decision.kind === 'assertion') expect(decision.assertion.reference).toBe(payload.ref);
        }
    });
});

describe('parseAssertionKeys', () => {
    it('reads the operator format and skips junk', () => {
        expect(parseAssertionKeys('1:one, 2:two:with:colons ,bad,:x,3:')).toEqual({ '1': 'one', '2': 'two:with:colons' });
        expect(parseAssertionKeys(undefined)).toEqual({});
    });
});
