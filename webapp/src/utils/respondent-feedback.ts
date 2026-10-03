/**
 * Respondent feedback ("Respond to submissions"): staff post a status from the
 * form's list and/or a message on a submission; its respondent sees it. The
 * rules mirror the backend (backend/app/services/respondent_feedback.py and
 * models/workspace.py normalize_feedback_statuses) — keep the two in step.
 */

export const DEFAULT_FEEDBACK_STATUSES = ['Under review', 'Selected', 'Rejected'];
export const MAX_FEEDBACK_STATUSES = 10;
export const MAX_FEEDBACK_STATUS_LENGTH = 40;
export const MAX_FEEDBACK_MESSAGE_LENGTH = 5000;

/** Collapse whitespace like the backend does before it compares statuses. */
export const cleanStatus = (status: string): string => status.split(/\s+/).filter(Boolean).join(' ');

/**
 * The status list as the backend will store it, or the reason it would be
 * refused: at most 10, each 1–40 characters, unique ignoring case.
 */
export function validateFeedbackStatuses(statuses: string[]): { statuses: string[]; error?: string } {
    const cleaned = statuses.map(cleanStatus);
    if (cleaned.length > MAX_FEEDBACK_STATUSES) return { statuses: cleaned, error: `At most ${MAX_FEEDBACK_STATUSES} statuses.` };
    const seen = new Set<string>();
    for (const status of cleaned) {
        if (status.length < 1 || status.length > MAX_FEEDBACK_STATUS_LENGTH) return { statuses: cleaned, error: `Each status must be 1 to ${MAX_FEEDBACK_STATUS_LENGTH} characters.` };
        const key = status.toLocaleLowerCase();
        if (seen.has(key)) return { statuses: cleaned, error: `"${status}" is listed twice.` };
        seen.add(key);
    }
    return { statuses: cleaned };
}

/** An update needs a status, a message or both; the message has a length cap. */
export function canSendFeedback(status: string | null | undefined, message: string | null | undefined): boolean {
    const text = (message ?? '').trim();
    return (!!status || text.length > 0) && text.length <= MAX_FEEDBACK_MESSAGE_LENGTH;
}

export type StatusTone = 'positive' | 'negative' | 'neutral';

/** A colour hint for a status chip, from common words; anything else is neutral. */
export function statusTone(status: string | null | undefined): StatusTone {
    const value = (status ?? '').toLocaleLowerCase();
    if (/(reject|declin|unsuccess|not selected|denied|refused)/.test(value)) return 'negative';
    if (/(select|accept|approv|hired|offer|success|complete|done|shortlist)/.test(value)) return 'positive';
    return 'neutral';
}

export const statusToneClass: Record<StatusTone, string> = {
    positive: 'bg-[#E7F4EE] text-[#0E8A5F]',
    negative: 'bg-[#FBEFEF] text-[#C43D3D]',
    neutral: 'bg-[#EAF0FD] text-[#2456CC]'
};

/** Who the respondent sees as the author: the organisation, never staff. */
export const feedbackAuthor = (author: string | null | undefined, fallback?: string | null): string => author || fallback || 'The team';
