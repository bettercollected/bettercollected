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

const RULE_LABELS: Record<string, (n: number) => string> = {
    other_option_gets_specify_field: (n) => `${n} "Other" option${n > 1 ? 's' : ''} got a "Please specify" field`,
    follow_up_shown_on_yes: (n) => `${n} follow-up question${n > 1 ? 's' : ''} shown only after "Yes"`,
    statement_verbatim: (n) => `${n} instruction${n > 1 ? 's' : ''} or declaration${n > 1 ? 's' : ''} kept word for word`,
    long_terms_to_terms_page: () => 'Long terms moved to a "Terms and declarations" page with an agreement',
    signature_to_typed_name_and_confirmation: (n) => `${n} signature${n > 1 ? 's' : ''} replaced by a typed full name and a confirmation`,
    bs_ad_date_pair_to_two_dates: (n) => `${n} B.S./A.D. date pair${n > 1 ? 's' : ''} split into two date fields`,
    location_sketch_to_questions: () => 'The location sketch became landmark, distance and direction questions',
    photo_box_to_upload: (n) => `${n} photo box${n > 1 ? 'es' : ''} became an image upload`,
    character_cells_to_text: (n) => `${n} character-box field${n > 1 ? 's' : ''} became text fields`,
    table_to_rows_of_fields: (n) => `${n} table${n > 1 ? 's' : ''} became rows of fields`,
    long_section_split: (n) => `${n} long section${n > 1 ? 's were' : ' was'} split across pages`,
    tiny_section_merged: (n) => `${n} short section${n > 1 ? 's were' : ' was'} merged into the page before`,
    theme_from_document: () => "The form's colours were taken from the document",
    staff_only_listed: (n) => `${n} staff-only part${n > 1 ? 's were' : ' was'} set aside`,
    consent: (n) => `${n} agreement${n > 1 ? 's' : ''} added`
};

export function describeRules(rules: Record<string, number> | undefined): string[] {
    return Object.entries(rules ?? {})
        .filter(([, n]) => n > 0)
        .map(([key, n]) => (RULE_LABELS[key] ? RULE_LABELS[key](n) : `${key.replace(/_/g, ' ')} (${n})`));
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
    if (!ACCEPTED_TYPES.includes(file.type) && !byName) return 'Choose a PDF, or a PNG, JPEG or WebP photo of a form.';
    if (file.size === 0) return 'This file is empty.';
    if (file.size > MAX_UPLOAD_BYTES) return 'This file is larger than 15 MB.';
    return null;
}

/** A review box whose wording the AI wrote (not found in the document's text). */
export function isAiWording(box: { grounded?: boolean | null }): boolean {
    return box.grounded === false;
}

/** The progress and review screens say whether the AI read the document. */
export function aiStructuringNote(aiConsent: boolean | undefined): string {
    return aiConsent ? 'AI structuring: on' : 'AI structuring: off (built-in reader only)';
}

/** Pages where words were kept out of the questions because they looked like filled-in answers. */
export function describeWithheld(withheld: Record<string, number> | undefined | null): { page: number; text: string }[] {
    return Object.entries(withheld ?? {})
        .map(([page, count]) => ({ page: Number(page), count: Number(count) }))
        .filter((w) => w.page > 0 && w.count > 0)
        .sort((a, b) => a.page - b.page)
        .map(({ page, count }) => ({
            page,
            text: `Page ${page}: ${count} ${count === 1 ? 'word' : 'words'} inside answer boxes looked like filled-in answers and ${count === 1 ? 'was' : 'were'} left out of the questions. Check the questions there.`
        }));
}
