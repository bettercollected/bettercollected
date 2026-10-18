import { NextResponse } from 'next/server';

import { createApi } from 'unsplash-js';

import { message, notConfigured, parseSearchParams, searchLimiter, signedInUserId, signInRequired, tooMany } from '@app/lib/server/unsplash';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

export const dynamic = 'force-dynamic';

/** The image picker's Unsplash search, for signed-in people only. */
export async function GET(request: Request) {
    const userId = await signedInUserId();
    if (!userId) return signInRequired();
    if (!unsplashAccessKey) return notConfigured();

    const parsed = parseSearchParams(new URL(request.url).searchParams);
    if ('error' in parsed) return message(parsed.error, 400);

    const verdict = searchLimiter.hit(userId);
    if (!verdict.allowed) return tooMany(verdict);

    const { query, page, perPage } = parsed.value;
    try {
        const unsplash = createApi({ accessKey: unsplashAccessKey });
        const { data: photos, error } = await unsplash.GET('/search/photos', {
            params: {
                query: {
                    page,
                    per_page: perPage,
                    query,
                    orientation: 'landscape'
                }
            }
        });
        if (error || !photos) return message('Image search is unavailable right now.', 502);
        return NextResponse.json(photos, { status: 200 });
    } catch (error) {
        // never the query: it is what the person typed
        console.error('Unsplash search failed:', error instanceof Error ? error.name : 'unknown error');
        return message('Image search is unavailable right now.', 500);
    }
}
