import type { PromotionProblem } from '@app/store/workspaces/form-promotion-api';

/**
 * The server's refusals of a copy (backend services/form_promotion), as the kinds the dialog words. Every code the routes
 * can answer has a sentence under `FORM_PROMOTION.ERROR.<KIND>` in both languages; anything else is `unknown`.
 */
export const PROMOTION_FAILURES = [
    'target_not_restricted',
    'promotion_from_restricted_form',
    'retention_confirmation_required',
    'target_changed',
    'precondition_failed',
    'form_promotion_disabled',
    'invalid_spec',
    'form_not_promotable',
    'same_form',
    'promotion_needs_session',
    'rate_limited',
    'audit_unavailable',
    'idempotency_in_progress',
    'not_found',
    'unknown'
] as const;

export type PromotionFailureKind = (typeof PROMOTION_FAILURES)[number];

export interface PromotionFailure {
    kind: PromotionFailureKind;
    /** `invalid_spec` carries every problem of the target's checks. */
    problems: PromotionProblem[];
}

const KNOWN = new Set<string>(PROMOTION_FAILURES);

/** The key of the sentence for a failure (`FORM_PROMOTION.ERROR.<KIND>`). */
export const failureKey = (kind: PromotionFailureKind): string => `FORM_PROMOTION.ERROR.${kind.toUpperCase()}`;

/** What a failed call means for the dialog. The code of the body decides, then the status; never the server's English text. */
export function failureOf(error: unknown): PromotionFailure {
    const { status, data } = (error ?? {}) as { status?: unknown; data?: { code?: unknown; errors?: unknown } | null };
    const code = typeof data?.code === 'string' ? data.code : '';
    const problems = code === 'invalid_spec' && Array.isArray(data?.errors) ? (data!.errors as PromotionProblem[]).filter((p) => p && typeof p.message === 'string') : [];
    if (KNOWN.has(code) && code !== 'not_found' && code !== 'unknown') return { kind: code as PromotionFailureKind, problems };
    if (status === 404) return { kind: 'not_found', problems };
    if (status === 429) return { kind: 'rate_limited', problems };
    if (status === 412) return { kind: 'precondition_failed', problems };
    return { kind: 'unknown', problems };
}

/** The refusals that mean the review on screen is out of date: the dialog reviews again instead of asking the person to. */
export const isStale = (kind: PromotionFailureKind): boolean => kind === 'precondition_failed';

/** "Page 2, question 3" for a JSON pointer into the form file (`/pages/1/fields/2`), when it names one. */
export function whereOf(path: string | null | undefined): { page: number; question?: number } | null {
    const found = /^\/pages\/(\d{1,4})(?:\/fields\/(\d{1,4}))?/.exec(path ?? '');
    if (!found) return null;
    return { page: Number(found[1]) + 1, question: found[2] === undefined ? undefined : Number(found[2]) + 1 };
}

/**
 * A fresh Idempotency-Key (printable ASCII, short, unguessable): `crypto.randomUUID()`, else 16 bytes of
 * `crypto.getRandomValues` as hex. No weaker source is used: without a secure random source it throws, and the copy is
 * not sent.
 */
export function newIdempotencyKey(): string {
    const c: Crypto | undefined = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
    if (c && typeof c.randomUUID === 'function') return c.randomUUID();
    if (c && typeof c.getRandomValues === 'function') {
        return Array.from(c.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('');
    }
    throw new Error('No secure random source for the Idempotency-Key');
}

/** A dashboard address in another workspace, every part encoded as one path segment (names and ids come from the server). */
export function dashboardFormUrl(workspaceName: string, formId: string, tail = ''): string {
    return `/${encodeURIComponent(workspaceName)}/dashboard/forms/${encodeURIComponent(formId)}${tail}`;
}
