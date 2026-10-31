import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import type { DraftContent, OpenedDraft } from '@app/store/redux/drafts-api';

/**
 * Save and continue later, as the respondent page sees it (backend
 * services/form_drafts). A draft holds the answers, the hidden-field values
 * and where the respondent was, by page id, so a changed form still finds its
 * pages. Files are never saved; calculated answers are the form's to compute.
 */

/** Days a draft is kept when the form does not say (backend limits.DEFAULT_RETENTION_DAYS). */
export const DEFAULT_DRAFT_DAYS = 30;

type FormSettings = StandardFormDto['settings'] | undefined;
type Answers = Record<string, any>;

/** Days the form keeps a draft: its setting when valid (1 to 90), else the default. */
export function draftDays(settings: FormSettings): number {
    const days = settings?.draftRetentionDays;
    return typeof days === 'number' && Number.isInteger(days) && days >= 1 && days <= 90 ? days : DEFAULT_DRAFT_DAYS;
}

/**
 * Whether the page offers "Save and continue later": the form lets
 * respondents, and (a form that asks for a verified identity sends no emailed
 * links) the respondent is signed in when it does.
 */
export function draftsOffered(settings: FormSettings, signedIn: boolean): boolean {
    if (!settings?.allowSaveDraft) return false;
    return signedIn || !settings.requireVerifiedIdentity;
}

const pageFields = (slides?: StandardFormFieldDto[]): StandardFormFieldDto[] => (slides ?? []).flatMap((slide) => slide?.properties?.fields ?? []);

/** Questions by id, group questions included; internal fields are staff-only and have no answers. */
function questionsById(slides?: StandardFormFieldDto[]): Map<string, StandardFormFieldDto> {
    const byId = new Map<string, StandardFormFieldDto>();
    pageFields(slides).forEach((field) => {
        if (!field?.id || field.internal) return;
        byId.set(field.id, field);
        if (field.type === FieldTypes.GROUP) field.properties?.fields?.forEach((child) => child?.id && !child.internal && byId.set(child.id, child));
    });
    return byId;
}

/** Whether a question's answer is the respondent's to keep in a draft (not a file, not a calculation). */
const savable = (field?: StandardFormFieldDto) => !!field && field.type !== FieldTypes.FILE_UPLOAD && field.type !== FieldTypes.CALCULATED;

export const hasFileQuestion = (slides?: StandardFormFieldDto[]): boolean => Array.from(questionsById(slides).values()).some((field) => field.type === FieldTypes.FILE_UPLOAD);

/** The answers a draft keeps: those of questions the form has now, without files and calculations. */
export function answersForDraft(slides: StandardFormFieldDto[] | undefined, answers: Answers | undefined): Answers {
    return restorable(slides, answers ?? {}).answers;
}

function restorable(slides: StandardFormFieldDto[] | undefined, answers: Answers): { answers: Answers; dropped: number } {
    const questions = questionsById(slides);
    const kept: Answers = {};
    let dropped = 0;
    Object.entries(answers).forEach(([id, answer]) => {
        const field = questions.get(id);
        if (!field) {
            dropped += 1;
            return;
        }
        if (!savable(field)) return;
        if (field.type === FieldTypes.GROUP && Array.isArray(answer?.items)) {
            const items = answer.items.map((item: Answers) => {
                const keptItem: Answers = {};
                Object.entries(item ?? {}).forEach(([childId, childAnswer]) => {
                    if (savable(questions.get(childId))) keptItem[childId] = childAnswer;
                    else if (!questions.has(childId)) dropped += 1;
                });
                return keptItem;
            });
            kept[id] = { ...answer, items };
            return;
        }
        kept[id] = answer;
    });
    return { answers: kept, dropped };
}

/** Where the respondent is, as the draft stores it: page ids, the welcome page left out. */
export function positionForDraft(slides: StandardFormFieldDto[] | undefined, currentSlide: number, history: number[] | undefined): NonNullable<DraftContent['position']> {
    const idOf = (index: number) => (index >= 0 ? slides?.[index]?.id : undefined);
    return {
        pageId: idOf(currentSlide) ?? null,
        history: (history ?? []).map(idOf).filter((id): id is string => !!id)
    };
}

export interface RestoredDraft {
    answers: Answers;
    hiddenFields: Record<string, string>;
    /** The page to open, and the pages visited before it (-1 is the welcome page). */
    slide: number;
    history: number[];
    /** Answers the form no longer has a question for. */
    dropped: number;
}

/** A draft put on the form as it is now: unknown questions and pages dropped, names not declared ignored. */
export function restoreDraft(form: Pick<StandardFormDto, 'fields' | 'hiddenFields'>, draft: Pick<OpenedDraft, 'answers' | 'hiddenFields' | 'position'>): RestoredDraft {
    const slides = form.fields ?? [];
    const { answers, dropped } = restorable(slides, draft.answers ?? {});
    const declared = new Set(form.hiddenFields ?? []);
    const hiddenFields = Object.fromEntries(Object.entries(draft.hiddenFields ?? {}).filter(([name]) => declared.has(name)));
    const indexOf = (id?: string | null) => (id ? slides.findIndex((slide) => slide.id === id) : -1);
    const page = indexOf(draft.position?.pageId);
    // a page that is gone: start at the first one, with nothing to go back through
    const visited = page < 0 ? [] : (draft.position?.history ?? []).map(indexOf).filter((index) => index >= 0 && index !== page);
    return { answers, hiddenFields, slide: Math.max(page, 0), history: [-1, ...visited], dropped };
}

/** The respondent's own fragment `#resume=<token>`, or null. */
export function resumeTokenOf(hash: string): string | null {
    const match = /^#resume=([0-9a-f]{24}\.[A-Za-z0-9_-]{43})$/.exec(hash);
    return match ? match[1] : null;
}

let taken: { token: string; at: number } | null = null;

/**
 * The link's token, taken from the address bar and kept in memory: read once
 * and the fragment removed from the address bar and the history entry at once,
 * before the form has loaded (a slow or failed fetch must not leave a
 * credential in the address bar). Call it where the page starts. A development
 * double render calls it again after the fragment is gone, so a token taken a
 * moment ago is handed out again.
 */
export function takeResumeToken(now: number = Date.now()): string | null {
    if (typeof window === 'undefined') return null;
    const token = resumeTokenOf(window.location.hash);
    if (token) {
        taken = { token, at: now };
        window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
        return token;
    }
    return taken && now - taken.at < 2000 ? taken.token : null;
}

/** Forget a token taken (for tests). */
export function forgetResumeToken(): void {
    taken = null;
}

/** The translation key (respondent namespace) for why a draft request failed. */
export function draftErrorKey(error: unknown): string {
    const failure = error as { status?: number; data?: { code?: string } } | undefined;
    const code = failure?.data?.code;
    switch (failure?.status) {
        case 429:
            return 'DRAFT.ERR_RATE';
        case 413:
            return 'DRAFT.ERR_TOO_LARGE';
        case 403:
            return 'DRAFT.ERR_SIGN_IN';
        case 503:
            return code === 'link_not_sent' ? 'DRAFT.ERR_LINK_NOT_SENT' : 'DRAFT.ERR_FAILED';
        case 422:
            return code === 'invalid_email' ? 'DRAFT.ERR_EMAIL' : 'DRAFT.ERR_FAILED';
        case 409:
            if (code === 'draft_limit') return 'DRAFT.ERR_LIMIT';
            return code === 'drafts_off' ? 'DRAFT.ERR_OFF' : 'DRAFT.ERR_CLOSED';
        case 404:
            return code === 'drafts_off' ? 'DRAFT.ERR_OFF' : 'DRAFT.ERR_NOT_FOUND';
        default:
            return 'DRAFT.ERR_FAILED';
    }
}

/** How long a magic link works (backend limits.LINK_LIFETIME). */
export const DRAFT_LINK_DAYS = 7;

/** A day for the respondent, in their language ("3 November 2026"); empty when it is not a date. */
export function formatDraftDate(iso: string | undefined, language: string): string {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat(language === 'nl' ? 'nl-NL' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' }).format(date);
}

/** What a creator typed for the days a draft is kept: empty = the default, else a whole number from 1 to 90. */
export function parseDraftDays(text: string): { value: number | null; error?: true } {
    const trimmed = text.trim();
    if (!trimmed) return { value: null };
    if (!/^\d{1,3}$/.test(trimmed)) return { value: null, error: true };
    const value = Number(trimmed);
    return value >= 1 && value <= 90 ? { value } : { value: null, error: true };
}
