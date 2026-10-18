/**
 * Shared checks for the image picker's Unsplash routes (app/api/unsplash).
 *
 * Both routes spend the server's UNSPLASH_ACCESS_KEY quota, so they answer
 * signed-in people only, with bounded parameters and a per-person limit.
 * Respondents never reach them: forms load Unsplash photos through the
 * backend's /images/unsplash route, which has its own limits.
 */
import { NextResponse } from 'next/server';

import { getUser } from '@app/lib/server/api';
import { createRateLimiter, RateLimitVerdict } from '@app/lib/server/rate-limit';

export const MAX_PER_PAGE = 30;
export const MAX_PAGE = 1000;
export const MAX_QUERY_LENGTH = 100;
// a request body larger than this is no photo reference
export const MAX_DOWNLOAD_BODY_BYTES = 16 * 1024;

const WINDOW_MS = 10 * 60 * 1000;
export const searchLimiter = createRateLimiter({ limit: 60, windowMs: WINDOW_MS });
export const downloadLimiter = createRateLimiter({ limit: 60, windowMs: WINDOW_MS });

/**
 * The id of the person signed in with this request's session cookies, as the
 * backend's /auth/status answers it; null without a valid session. Only the
 * session cookies count, never a header the caller sets.
 */
export async function signedInUserId(): Promise<string | null> {
    const user = await getUser();
    return typeof user?.id === 'string' && user.id ? user.id : null;
}

export function message(text: string, status: number, headers?: Record<string, string>) {
    return NextResponse.json({ message: text }, { status, headers });
}

export function signInRequired() {
    return message('Sign in to search images.', 401);
}

export function notConfigured() {
    return message('Image search is not configured.', 503);
}

export function tooMany(verdict: RateLimitVerdict) {
    return message('Too many image requests. Try again in a few minutes.', 429, { 'Retry-After': String(verdict.retryAfterSeconds) });
}

export interface SearchParams {
    query: string;
    page: number;
    perPage: number;
}

const WHOLE_NUMBER = /^\d{1,6}$/;

/** The search's parameters, bounded, or a message saying what is wrong. */
export function parseSearchParams(params: URLSearchParams): { value: SearchParams } | { error: string } {
    const query = (params.get('query') ?? '').trim();
    if (!query) return { error: 'Pass a query.' };
    if (query.length > MAX_QUERY_LENGTH) return { error: `The query is longer than ${MAX_QUERY_LENGTH} characters.` };

    const rawPage = params.get('page') ?? '1';
    if (!WHOLE_NUMBER.test(rawPage)) return { error: 'The page must be a whole number.' };
    const page = parseInt(rawPage, 10);
    if (page < 1 || page > MAX_PAGE) return { error: `The page must be between 1 and ${MAX_PAGE}.` };

    const rawPerPage = params.get('perPage') ?? String(MAX_PER_PAGE);
    if (!WHOLE_NUMBER.test(rawPerPage)) return { error: 'perPage must be a whole number.' };
    const perPage = parseInt(rawPerPage, 10);
    if (perPage < 1) return { error: 'perPage must be at least 1.' };

    return { value: { query, page, perPage: Math.min(perPage, MAX_PER_PAGE) } };
}
