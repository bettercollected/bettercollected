// Pure helpers of the email action screens (docs/email-actions.md): the same
// placeholder and recipient syntax the server applies (the server decides; this
// only tells people early) and the translation keys of what it answers.

export const NAME_MAX = 80;
export const SUBJECT_MAX = 200;
export const BODY_MAX = 10_000;
export const MAX_TEAM = 5;
export const BUILT_INS_SUBJECT = ['form_title', 'submitted_at'] as const;
export const BUILT_INS_BODY = ['form_title', 'submitted_at', 'answers'] as const;
export const PLACEHOLDER = /\{\{\s*([A-Za-z_][A-Za-z0-9_]{0,63})\s*\}\}/g;

export const ERROR_CODES = [
    'email_actions_off',
    'mail_not_configured',
    'invalid_recipient',
    'recipient_not_allowed',
    'too_many_recipients',
    'no_recipient',
    'invalid_respondent_field',
    'unknown_placeholder',
    'invalid_placeholder',
    'template_missing',
    'invalid_name',
    'invalid_key',
    'unknown_variable',
    'variable_not_supported',
    'file_not_sent',
    'too_many_fields',
    'too_many_actions',
    'invalid_condition',
    'no_copy',
    'no_address',
    'rate_limited',
    'forbidden',
    'not_found'
] as const;

export const DELIVERY_ERROR_CODES = [
    'recipient_rejected',
    'smtp_rejected',
    'smtp_busy',
    'smtp_auth',
    'smtp_unavailable',
    'smtp_error',
    'timeout',
    'tls_error',
    'invalid_message',
    'mail_not_configured',
    'answers_unreadable',
    'recipient_not_allowed',
    'no_address',
    'rate_limited',
    'disabled',
    'condition_not_met',
    'condition_invalid',
    'internal_error'
] as const;

const isKnown = (list: readonly string[], code: unknown): code is string => typeof code === 'string' && list.includes(code);

export const errorKey = (code: unknown) => `EMAIL_ACTIONS.ERROR.${isKnown(ERROR_CODES, code) ? code : 'unknown'}`;
export const deliveryErrorKey = (code?: string | null) => `EMAIL_ACTIONS.DELIVERIES.ERROR.${isKnown(DELIVERY_ERROR_CODES, code) ? code : 'unknown'}`;

export type EditorField = 'name' | 'recipients' | 'respondent' | 'templates' | 'fields' | 'condition';

/** Which part of the editor a refusal belongs to (so it sits next to it), or null for the form as a whole. */
export function errorField(code: string): EditorField | null {
    switch (code) {
        case 'invalid_name':
            return 'name';
        case 'invalid_recipient':
        case 'recipient_not_allowed':
        case 'too_many_recipients':
        case 'no_recipient':
            return 'recipients';
        case 'invalid_respondent_field':
            return 'respondent';
        case 'unknown_placeholder':
        case 'invalid_placeholder':
        case 'template_missing':
            return 'templates';
        case 'invalid_key':
        case 'unknown_variable':
        case 'variable_not_supported':
        case 'file_not_sent':
        case 'too_many_fields':
            return 'fields';
        case 'invalid_condition':
            return 'condition';
        default:
            return null;
    }
}

/** Addresses typed one per line (commas, semicolons and spaces also separate), trimmed, each once. */
export function parseRecipients(text: string): string[] {
    const found: string[] = [];
    for (const part of text.split(/[\s,;]+/)) {
        const address = part.trim();
        if (address && !found.some((a) => a.toLowerCase() === address.toLowerCase())) found.push(address);
    }
    return found;
}

/** One plain address: one `@`, something either side, no spaces or the characters of a name or list. */
export function addressProblem(value: string): boolean {
    return !/^[^\s@<>(),;:"\\[\]]+@[^\s@<>(),;:"\\[\]]+$/.test(value) || value.length > 254;
}

/** The placeholders a template may use: the mapped keys and the built-ins. */
export function placeholdersFor(keys: string[], part: 'subject' | 'body'): string[] {
    return [...keys, ...(part === 'subject' ? BUILT_INS_SUBJECT : BUILT_INS_BODY)];
}

/** The first thing wrong with a template ({{unknown}} or stray braces), or null; the same rule as the server. */
export function templateProblem(text: string, allowed: string[]): { code: 'unknown_placeholder' | 'invalid_placeholder'; name?: string } | null {
    for (const match of text.matchAll(PLACEHOLDER)) {
        if (!allowed.includes(match[1])) return { code: 'unknown_placeholder', name: match[1] };
    }
    const rest = text.replace(PLACEHOLDER, '');
    if (rest.includes('{{') || rest.includes('}}')) return { code: 'invalid_placeholder' };
    return null;
}

/** `text` with `{{name}}` put where the selection is (replacing it); returns the new text and where the cursor goes. */
export function insertPlaceholder(text: string, name: string, start: number, end: number): { text: string; cursor: number } {
    const at = Math.max(0, Math.min(start, text.length));
    const to = Math.max(at, Math.min(end, text.length));
    const token = `{{${name}}}`;
    return { text: text.slice(0, at) + token + text.slice(to), cursor: at + token.length };
}

export const DEFAULT_TEMPLATES = {
    en: { subject: 'New response to {{form_title}}', body: 'A new response was submitted to {{form_title}} at {{submitted_at}}.\n\n{{answers}}' },
    nl: { subject: 'Nieuwe inzending voor {{form_title}}', body: 'Er is een nieuwe inzending gedaan voor {{form_title}} op {{submitted_at}}.\n\n{{answers}}' }
};

export const LANGUAGES = ['en', 'nl'] as const;
export type TemplateLanguage = (typeof LANGUAGES)[number];

export const CHANNEL_KEY = (channel?: string | null) => `EMAIL_ACTIONS.DELIVERIES.CHANNEL.${channel === 'respondent' ? 'respondent' : 'team'}`;
