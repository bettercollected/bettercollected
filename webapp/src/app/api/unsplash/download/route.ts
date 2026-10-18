import { NextResponse } from 'next/server';

import { createApi } from 'unsplash-js';

import { downloadLimiter, MAX_DOWNLOAD_BODY_BYTES, message, notConfigured, signedInUserId, signInRequired, tooMany } from '@app/lib/server/unsplash';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

// Unsplash photo ids are short url-safe strings (e.g. "mtNweauBsMQ").
const PHOTO_ID = /^[A-Za-z0-9_-]{1,64}$/;

export const dynamic = 'force-dynamic';

/** The picked photo's id from a small JSON body, or '' for anything else. */
async function photoId(request: Request): Promise<string> {
    const declared = Number(request.headers.get('content-length') ?? '0');
    if (declared > MAX_DOWNLOAD_BODY_BYTES) return '';
    const body = await request.text();
    if (body.length > MAX_DOWNLOAD_BODY_BYTES) return '';
    try {
        const photo = JSON.parse(body);
        return typeof photo?.id === 'string' ? photo.id : '';
    } catch {
        return '';
    }
}

/**
 * Tells Unsplash a photo was picked, as its API guidelines ask, for signed-in
 * people only.
 */
export async function POST(request: Request) {
    const userId = await signedInUserId();
    if (!userId) return signInRequired();
    if (!unsplashAccessKey) return notConfigured();

    const id = await photoId(request);
    if (!PHOTO_ID.test(id)) return message('Invalid photo.', 400);

    const verdict = downloadLimiter.hit(userId);
    if (!verdict.allowed) return tooMany(verdict);

    try {
        const unsplash = createApi({ accessKey: unsplashAccessKey });
        const { data, error } = await unsplash.GET('/photos/{id}/download', { params: { path: { id } } });
        if (error) return message('Unsplash did not accept the download.', 502);
        return NextResponse.json(data, { status: 200 });
    } catch (error) {
        console.error('Unsplash download tracking failed:', error instanceof Error ? error.name : 'unknown error');
        return message('Unsplash is unavailable right now.', 500);
    }
}
