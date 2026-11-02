import { isSameSitePath } from '@app/utils/same-site-path';

/** What the second-factor routes answer with when they refuse (docs/totp.md). */
export interface MfaFailure {
    status?: number;
    // invalid_code, mfa_locked, too_many_attempts, mfa_challenge_expired, recent_proof_required, totp_off, no_factor
    code?: string;
    // seconds until another attempt is allowed (429)
    retryAfter?: number;
}

/** The refusal in an RTK Query error: its HTTP status, `code` and the wait. Never throws. */
export function mfaFailureOf(error: unknown): MfaFailure {
    const failure = error as { status?: unknown; data?: { code?: unknown; retry_after?: unknown; retryAfter?: unknown } } | undefined;
    const data = failure?.data && typeof failure.data === 'object' ? failure.data : undefined;
    const wait = Number(data?.retry_after ?? data?.retryAfter);
    return {
        status: typeof failure?.status === 'number' ? failure.status : undefined,
        code: typeof data?.code === 'string' ? data.code : undefined,
        retryAfter: Number.isFinite(wait) && wait > 0 ? wait : undefined
    };
}

/** Whole minutes to wait (at least one) for `seconds`. */
export function waitMinutes(seconds: number | undefined, fallback = 15): number {
    return Math.max(1, Math.ceil((seconds && seconds > 0 ? seconds : fallback * 60) / 60));
}

/** Whether a sign-in answer says that a second factor is still needed. */
export function isMfaRequired(answer: unknown): boolean {
    return !!answer && typeof answer === 'object' && (answer as { mfaRequired?: unknown }).mfaRequired === true;
}

/** A recovery code is 16 letters and digits, shown in groups of four ("ABCD-EFGH-IJKL-MNOP"). */
export function looksLikeRecoveryCode(value: string): boolean {
    return /^[A-Za-z0-9]{16}$/.test(value.replace(/[\s-]/g, ''));
}

/** What to send for what was typed: the six digits without spaces, or the recovery code with its dashes. */
export function normaliseCode(value: string, recovery: boolean): string {
    const trimmed = value.trim();
    if (!recovery) return trimmed.replace(/\s+/g, '');
    return trimmed.replace(/\s+/g, '').toUpperCase();
}

/**
 * Where a completed sign-in goes, from the `next` the server put on the login
 * address: a path of this app. The server only sends addresses it allows, but
 * the page does not rely on that: an address of this origin becomes its path,
 * anything else is dropped (the caller reloads the sign-in page, which decides).
 */
export function safeNextPath(next: string | null | undefined, origin?: string): string | undefined {
    if (!next) return undefined;
    const here = origin ?? (typeof window !== 'undefined' ? window.location.origin : undefined);
    if (!here) return undefined;
    if (isSameSitePath(next, here)) return next;
    try {
        const url = new URL(next);
        if (url.origin !== here) return undefined;
        const path = `${url.pathname}${url.search}${url.hash}`;
        return isSameSitePath(path, here) ? path : undefined;
    } catch {
        return undefined;
    }
}
