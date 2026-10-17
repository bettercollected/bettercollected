// What building a form from an AI outline left to check, carried from the
// Start with AI dialog to the editor (sessionStorage, per form). Only codes,
// severities, ids and the backend's notes (counts, never form text) are kept.

export interface BuildFinding {
    code: string;
    severity: string;
    where: string[];
}

export interface BuildReport {
    notes: string[];
    findings: BuildFinding[];
}

const key = (formId: string) => `bc:ai-build:${formId}`;

function storage(): Storage | null {
    try {
        return typeof window === 'undefined' ? null : window.sessionStorage;
    } catch {
        return null;
    }
}

export function saveBuildReport(formId: string, report: { notes?: string[]; quality?: { findings?: { code: string; severity: string; where?: string[] }[] } }): boolean {
    const findings = (report.quality?.findings ?? []).map((f) => ({ code: String(f.code), severity: String(f.severity), where: (f.where ?? []).map(String).slice(0, 10) }));
    const notes = (report.notes ?? []).map(String).slice(0, 20);
    if (!findings.length && !notes.length) return false;
    try {
        storage()?.setItem(key(formId), JSON.stringify({ notes, findings }));
        return true;
    } catch {
        return false;
    }
}

export function readBuildReport(formId: string): BuildReport | null {
    try {
        const raw = storage()?.getItem(key(formId));
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || !Array.isArray(parsed.notes) || !Array.isArray(parsed.findings)) return null;
        return parsed as BuildReport;
    } catch {
        return null;
    }
}

export function hasBuildReport(formId: string): boolean {
    return readBuildReport(formId) !== null;
}

export function clearBuildReport(formId: string): void {
    try {
        storage()?.removeItem(key(formId));
    } catch {
        // nothing to clear
    }
}

// Plain-language text per quality finding code (backend services/ai/quality.py).
const FINDING_TEXT: Record<string, string> = {
    missing_title: 'The form has no title.',
    no_questions: 'The form has no question to answer yet.',
    too_many_questions_on_page: 'A page has many questions. Consider splitting it.',
    too_many_questions: 'The form has more questions than you asked for.',
    missing_field_type: 'A kind of question your request implied is missing.',
    missing_section_titles: 'Some pages have no section title.',
    wrong_language: 'The form reads in another language than you asked for.',
    mixed_language: 'The form mixes languages.',
    duplicate_question: 'Two questions ask the same thing.',
    optional_marked_required: 'A question that says it is optional is required.',
    all_required: 'Every question is required. Keep optional what you do not need.',
    too_few_choices: 'A choice question needs at least two options.',
    external_image: 'The form loads an image from another website.',
    external_image_dropped: 'An image from another website was left out.',
    dangling_logic_reference: 'A rule refers to a question or page that does not exist.',
    theme_not_default: 'The form does not use the Leaflet look.',
    theme_request_ignored: 'The form kept the default look, though you asked for another one.',
    missing_why_we_ask: 'A question asks for an email, phone or ID number without saying why. Add a "why we ask" line before publishing.',
    required_unanswerable: 'A required question cannot be answered.',
    preset_answer: 'A choice question starts with an answer already chosen.'
};

export function findingText(code: string): string {
    return FINDING_TEXT[code] ?? 'Something on this form needs a look before publishing.';
}
