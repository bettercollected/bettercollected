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

import { getWorkspaceByDomain, getWorkspaceById } from '@app/lib/server/api';
import { ASSERTION_HEADER, Assertion, AssertionErrorCode, customDomainConfig, decideAssertion } from '@app/lib/server/custom-domain-assertion';

// The verifier and the decision live in custom-domain-assertion.ts (pure, also used by the proxy).
export * from '@app/lib/server/custom-domain-assertion';

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
    const decision = decideAssertion(headerList.get(ASSERTION_HEADER), config, host);
    if (decision.kind === 'legacy') {
        return { workspace: await getWorkspaceByDomain(host), assertion: null };
    }
    if (decision.kind === 'refused') {
        console.warn(`custom domain request refused: ${decision.error}`);
        return { workspace: null, assertion: null, error: decision.error };
    }
    const workspace = await getWorkspaceById(decision.assertion.reference);
    return { workspace: workspace?.id ? workspace : null, assertion: decision.assertion };
}

