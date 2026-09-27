/**
 * The workspace probe (custom-domain service, docs/lifecycle.md): reached as
 * /.well-known/custom-domain-workspace through the edge, with an assertion.
 * A domain becomes ready only when this answers with the reference the
 * assertion carries and that workspace really exists.
 */
import { NextRequest, NextResponse } from 'next/server';

import { getWorkspaceById } from '@app/lib/server/api';
import { ASSERTION_HEADER, AssertionInvalid, customDomainConfig, verifyAssertion } from '@app/lib/server/custom-domain';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
    const config = customDomainConfig();
    if (!config) return NextResponse.json({ error: 'not_configured' }, { status: 503 });
    const host = request.headers.get('x-forwarded-host') || request.headers.get('host');
    try {
        const assertion = verifyAssertion(request.headers.get(ASSERTION_HEADER), config.keys, { applicationId: config.applicationId, hostname: host });
        const workspace = await getWorkspaceById(assertion.reference);
        if (!workspace?.id) return NextResponse.json({ error: 'workspace_not_found' }, { status: 404 });
        return NextResponse.json({ reference: assertion.reference, application: assertion.applicationId });
    } catch (error) {
        const code = error instanceof AssertionInvalid ? error.code : 'malformed';
        return NextResponse.json({ error: `assertion_${code}` }, { status: 403 });
    }
}
