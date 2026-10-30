/**
 * Whether a failed API call was refused by a rate limit (HTTP 429). The
 * receipt routes answer 429 for a while after too many lookups, which must
 * not read as "no such submission".
 */
export function isRateLimited(error: unknown): boolean {
    return typeof error === 'object' && error !== null && (error as { status?: unknown }).status === 429;
}
