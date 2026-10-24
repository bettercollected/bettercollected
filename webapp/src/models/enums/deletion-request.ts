// Closing a deletion request by hand (backend: POST /workspaces/{id}/forms/
// {form_id}/submissions/{response_id}/deletion-request/close, privacy.manage).

/** `completed` deletes the copy stored here; `declined` keeps it, with a reason. */
export type DeletionRequestOutcome = 'completed' | 'declined';

/** Why staff declined (GDPR Art. 17(3), Art. 12(6)): a fixed list, never free text. */
export const DECLINE_REASONS = ['legal_obligation', 'legal_claims', 'public_interest', 'identity_not_verified', 'other'] as const;
export type DeclineReason = (typeof DECLINE_REASONS)[number];

export const isDeclineReason = (value: unknown): value is DeclineReason => typeof value === 'string' && (DECLINE_REASONS as ReadonlyArray<string>).includes(value);

/** A deletion request's status as the lists report it: pending, success (deleted) or declined. */
export const isPendingRequest = (status: string | null | undefined) => !status || status.toLowerCase() === 'pending';
export const isDeclinedRequest = (status: string | null | undefined) => status?.toLowerCase() === 'declined';

/** What a failed close means for the person who tried it. */
export type CloseDeletionRequestError = 'alreadyClosed' | 'copyUnresolved' | 'failed';

export function closeDeletionRequestError(error: unknown): CloseDeletionRequestError {
    const { status, data } = (error ?? {}) as { status?: number; data?: { code?: string } };
    if (status === 409 && data?.code === 'deletion_request_closed') return 'alreadyClosed';
    if (status === 409 && data?.code === 'deletion_request_copy_unresolved') return 'copyUnresolved';
    return 'failed';
}
