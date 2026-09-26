/**
 * Proof that this deployment is the origin registered with the custom-domain
 * service (`custom-domain origin register` prints the token). Served as
 * /.well-known/custom-domain-origin-verification, plain text, exactly the token.
 */
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
    const token = process.env.CUSTOM_DOMAIN_ORIGIN_VERIFICATION_TOKEN;
    if (!token) return new NextResponse('Not Found', { status: 404 });
    return new NextResponse(token, { status: 200, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
}
