/**
 * Custom-domain requests arrive through the custom-domain service's edge
 * (github.com/sireto/custom-domain), which adds a signed assertion naming the
 * workspace the hostname belongs to. The workspace is selected from that
 * assertion and never from the Host header, so nobody can be served another
 * tenant's forms by sending a Host header. This is a port of the SDK's
 * verifier (docs/edge-routing.md); the algorithm is HMAC-SHA256 over
 * `v1.<key id>.<payload>`, base64url, 60 s TTL with 30 s clock skew.
 *
 * Until the operator configures CUSTOM_DOMAIN_ASSERTION_KEYS and
 * CUSTOM_DOMAIN_APPLICATION_ID, the legacy host lookup stays in place.
 */
import { headers } from 'next/headers';

import { createHmac, timingSafeEqual } from 'node:crypto';

import { getWorkspaceByDomain, getWorkspaceById } from '@app/lib/server/api';

export const ASSERTION_HEADER = 'x-custom-domain-assertion';
const VERSION = 'v1';
const DEFAULT_SKEW = 30;

export interface Assertion {
    applicationId: string;
    domainId: string;
    reference: string;
    hostname: string;
    issuedAt: number;
    expiresAt: number;
    requestId: string;
    keyId: string;
}

export type AssertionErrorCode = 'missing' | 'malformed' | 'unknown_key' | 'bad_signature' | 'not_yet_valid' | 'expired' | 'wrong_application' | 'wrong_hostname';

export class AssertionInvalid extends Error {
    code: AssertionErrorCode;
    constructor(code: AssertionErrorCode, message: string) {
        super(message);
        this.code = code;
    }
}

function unb64(text: string): Buffer {
    return Buffer.from(text, 'base64url');
}

export function verifyAssertion(token: string | null | undefined, keys: Record<string, string>, options: { applicationId: string; hostname?: string | null; now?: number; skew?: number }): Assertion {
    if (!token) throw new AssertionInvalid('missing', 'No assertion header');
    const parts = token.split('.');
    if (parts.length !== 4 || parts[0] !== VERSION) throw new AssertionInvalid('malformed', 'Assertion is not a v1 token');
    const [, keyId, payload, signature] = parts;
    const secret = keys[keyId];
    if (secret === undefined) throw new AssertionInvalid('unknown_key', `Assertion signed with unknown key id ${keyId}`);
    const expected = createHmac('sha256', secret).update(`${VERSION}.${keyId}.${payload}`).digest();
    let given: Buffer;
    try {
        given = unb64(signature);
    } catch {
        throw new AssertionInvalid('malformed', 'Assertion signature is not base64url');
    }
    if (given.length !== expected.length || !timingSafeEqual(new Uint8Array(expected), new Uint8Array(given))) {
        throw new AssertionInvalid('bad_signature', 'Assertion signature does not verify');
    }
    let assertion: Assertion;
    try {
        const data = JSON.parse(unb64(payload).toString('utf8'));
        assertion = {
            applicationId: String(data.app),
            domainId: String(data.dom),
            reference: String(data.ref),
            hostname: String(data.host),
            issuedAt: Number(data.iat),
            expiresAt: Number(data.exp),
            requestId: String(data.rid),
            keyId
        };
        if (!Number.isFinite(assertion.issuedAt) || !Number.isFinite(assertion.expiresAt) || data.app === undefined || data.ref === undefined) {
            throw new Error('incomplete');
        }
    } catch {
        throw new AssertionInvalid('malformed', 'Assertion payload is not valid');
    }
    const skew = options.skew ?? DEFAULT_SKEW;
    const now = Math.floor(options.now ?? Date.now() / 1000);
    if (assertion.issuedAt > now + skew) throw new AssertionInvalid('not_yet_valid', 'Assertion issued in the future');
    if (assertion.expiresAt + skew < now) throw new AssertionInvalid('expired', 'Assertion has expired');
    if (assertion.applicationId !== options.applicationId) throw new AssertionInvalid('wrong_application', 'Assertion is for another application');
    if (options.hostname != null) {
        const host = options.hostname.split(':', 1)[0].toLowerCase().replace(/\.$/, '');
        if (assertion.hostname !== host) throw new AssertionInvalid('wrong_hostname', 'Assertion is for another hostname');
    }
    return assertion;
}

/** `<id>:<secret>,...` as the operator hands it out; every entry verifies. */
export function parseAssertionKeys(value: string | undefined): Record<string, string> {
    const keys: Record<string, string> = {};
    for (const item of (value || '').split(',')) {
        const index = item.indexOf(':');
        if (index > 0) {
            const id = item.slice(0, index).trim();
            const secret = item.slice(index + 1).trim();
            if (id && secret) keys[id] = secret;
        }
    }
    return keys;
}

export interface CustomDomainConfig {
    keys: Record<string, string>;
    applicationId: string;
}

export function customDomainConfig(): CustomDomainConfig | null {
    const keys = parseAssertionKeys(process.env.CUSTOM_DOMAIN_ASSERTION_KEYS);
    const applicationId = process.env.CUSTOM_DOMAIN_APPLICATION_ID || '';
    if (!applicationId || Object.keys(keys).length === 0) return null;
    return { keys, applicationId };
}

export type ResolvedCustomDomain = { workspace: any | null; assertion: Assertion | null; error?: AssertionErrorCode };

/**
 * The workspace this custom-domain request is for. With the service
 * configured, only a valid edge assertion selects a workspace (by its
 * reference, the workspace id); without it, the legacy lookup by host.
 */
export async function resolveCustomDomainWorkspace(): Promise<ResolvedCustomDomain> {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';
    const config = customDomainConfig();
    if (!config) {
        return { workspace: await getWorkspaceByDomain(host), assertion: null };
    }
    let assertion: Assertion;
    try {
        assertion = verifyAssertion(headerList.get(ASSERTION_HEADER), config.keys, { applicationId: config.applicationId, hostname: host });
    } catch (error) {
        const code = error instanceof AssertionInvalid ? error.code : 'malformed';
        console.warn(`custom domain request refused: ${code}`);
        return { workspace: null, assertion: null, error: code };
    }
    const workspace = await getWorkspaceById(assertion.reference);
    return { workspace: workspace?.id ? workspace : null, assertion };
}
