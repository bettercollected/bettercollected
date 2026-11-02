import i18n from 'i18next';

/**
 * Pure helpers for the PDF form import screens: progress through the
 * pipeline stages, the import report in plain words, and placing the
 * imported questions on a page image.
 */

export const STAGES: { key: string; label: string }[] = [
    { key: 'analyze', label: 'Reading the document' },
    { key: 'text', label: 'Recovering the text' },
    { key: 'layout', label: 'Finding boxes, tables and checkboxes' },
    { key: 'render', label: 'Preparing page images' },
    { key: 'structure', label: 'Recognising the questions' },
    { key: 'compile', label: 'Building your draft form' }
];

export type StageState = 'done' | 'current' | 'waiting' | 'failed';

export function stageStates(status: string, stage: string | null | undefined, finished: string[]): Record<string, StageState> {
    const out: Record<string, StageState> = {};
    for (const s of STAGES) {
        if (finished.includes(s.key)) out[s.key] = 'done';
        else if (status === 'failed' && s.key === (stage ?? '')) out[s.key] = 'failed';
        else if (status === 'running' && s.key === stage) out[s.key] = 'current';
        else out[s.key] = 'waiting';
    }
    if (status === 'completed') for (const s of STAGES) out[s.key] = 'done';
    return out;
}

export function progressPercent(states: Record<string, StageState>): number {
    const done = Object.values(states).filter((s) => s === 'done').length;
    const current = Object.values(states).some((s) => s === 'current') ? 0.5 : 0;
    return Math.round(((done + current) / STAGES.length) * 100);
}

// The wording of each rule is builder.json `PDF_REVIEW.RULE.<key>` (plural per count), in the builder's language.
const RULE_KEYS = new Set([
    'other_option_gets_specify_field',
    'follow_up_shown_on_yes',
    'statement_verbatim',
    'long_terms_to_terms_page',
    'signature_to_typed_name_and_confirmation',
    'bs_ad_date_pair_to_two_dates',
    'location_sketch_to_questions',
    'photo_box_to_upload',
    'character_cells_to_text',
    'open_table_to_repeating_group',
    'fixed_table_to_fields',
    'applicant_blocks_to_repeating_group',
    'applicant_blocks_prefixed',
    'staff_only_to_internal_fields',
    'long_section_split',
    'tiny_section_merged',
    'theme_from_document',
    'staff_only_listed',
    'consent'
]);

export function describeRules(rules: Record<string, number> | undefined): string[] {
    return Object.entries(rules ?? {})
        .filter(([, n]) => n > 0)
        .map(([key, n]) => (RULE_KEYS.has(key) ? i18n.t(`builder:PDF_REVIEW.RULE.${key}`, { count: n }) : `${key.replace(/_/g, ' ')} (${n})`));
}

/** A staff-only part of the paper form, as the review screen lists it. */
export function describeStaffPart(part: { heading?: string | null; internal_fields?: number | null }): string {
    const heading = part.heading?.trim() || i18n.t('builder:PDF_REVIEW.STAFF_PART');
    const n = Number(part.internal_fields ?? 0);
    if (n > 0) return i18n.t('builder:PDF_REVIEW.STAFF_FIELDS', { heading, count: n });
    return i18n.t('builder:PDF_REVIEW.STAFF_LEFT_OUT', { heading });
}

/** Where a box (PDF points, top-left origin) sits on an image displayed at `displayWidth` pixels. */
export function placeBox(bbox: [number, number, number, number], pageWidth: number, displayWidth: number) {
    const scale = pageWidth > 0 ? displayWidth / pageWidth : 1;
    const [x0, top, x1, bottom] = bbox;
    return { left: x0 * scale, top: top * scale, width: Math.max(2, (x1 - x0) * scale), height: Math.max(2, (bottom - top) * scale) };
}

export const ACCEPTED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp'];
export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export function validateUpload(file: { type: string; size: number; name: string }): string | null {
    const byName = /\.(pdf|png|jpe?g|webp)$/i.test(file.name);
    if (!ACCEPTED_TYPES.includes(file.type) && !byName) return i18n.t('builder:PDF_REVIEW.UPLOAD_TYPE');
    if (file.size === 0) return i18n.t('builder:PDF_REVIEW.UPLOAD_EMPTY');
    if (file.size > MAX_UPLOAD_BYTES) return i18n.t('builder:PDF_REVIEW.UPLOAD_LARGE');
    return null;
}

/** A review box whose wording the AI wrote (not found in the document's text). */
export function isAiWording(box: { grounded?: boolean | null }): boolean {
    return box.grounded === false;
}

/** The progress and review screens say whether the AI read the document. */
export function aiStructuringNote(aiConsent: boolean | undefined): string {
    return aiConsent ? i18n.t('builder:PDF_REVIEW.AI_ON') : i18n.t('builder:PDF_REVIEW.AI_OFF');
}

/** Pages where words were kept out of the questions because they looked like filled-in answers. */
export function describeWithheld(withheld: Record<string, number> | undefined | null): { page: number; text: string }[] {
    return Object.entries(withheld ?? {})
        .map(([page, count]) => ({ page: Number(page), count: Number(count) }))
        .filter((w) => w.page > 0 && w.count > 0)
        .sort((a, b) => a.page - b.page)
        .map(({ page, count }) => ({
            page,
            text: i18n.t('builder:PDF_REVIEW.WITHHELD', { page, count })
        }));
}

/** Reasons an import can stop with, each with its own message and next step (builder namespace, PDF_IMPORT.ERROR.<code>). */
export const IMPORT_ERROR_CODES = ['encrypted', 'unreadable', 'too_many_pages', 'too_large', 'too_complex', 'timeout', 'empty', 'unsupported_type', 'no_questions', 'unavailable', 'interrupted', 'failed'] as const;
export type ImportErrorCode = (typeof IMPORT_ERROR_CODES)[number];

/** Reasons the upload itself can be refused with, before an import starts (PDF_IMPORT.START_ERROR.<code>). */
export const START_ERROR_CODES = ['import_in_progress', 'daily_limit', 'too_large', 'unsupported_type', 'empty'] as const;

/** Why a failed import stopped: its error code (older records only have `report.refused`); anything unknown is a plain failure. */
export function importErrorCode(item: { errorCode?: string | null; report?: Record<string, any> | null }): ImportErrorCode {
    const code = item.errorCode ?? item.report?.refused ?? 'failed';
    return (IMPORT_ERROR_CODES as readonly string[]).includes(code) ? (code as ImportErrorCode) : 'failed';
}

/** Whether only the built-in reader ran: no consent for the upload, or the report says why AI was not used. */
export function readWithoutAi(item: { aiConsent?: boolean; report?: Record<string, any> | null }): boolean {
    const notes: unknown[] = item.report?.notes ?? [];
    return !item.aiConsent || notes.some((n) => typeof n === 'string' && n.startsWith('AI structuring not used'));
}

/** The translation key of what to do next after a failed import. */
export function importErrorNextKey(code: ImportErrorCode, withoutAi: boolean): string {
    if (code === 'no_questions' && withoutAi) return 'PDF_IMPORT.ERROR.no_questions.NEXT_WITHOUT_AI';
    return `PDF_IMPORT.ERROR.${code}.NEXT`;
}

/** The translation key for a refused upload, or null for an unknown code (the server's message is shown then). */
export function startErrorKey(code: string | null | undefined): string | null {
    if (code && (START_ERROR_CODES as readonly string[]).includes(code)) return `PDF_IMPORT.START_ERROR.${code}`;
    return null;
}
