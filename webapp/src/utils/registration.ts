import type { RegistrationAuth, RegistrationService, RegistrationVariable } from '@app/store/workspaces/registration-api';

// Sending submissions to a case system: the codes the API answers with and
// the translation key of the sentence each one gets (builder.json,
// REGISTRATION.*). The API's own `message` is never shown: it is English and
// ours to word, so every code has a sentence in both languages.

/** Refusals of a service call or a form's settings (422/409/404/403/410). */
export const ERROR_CODES = [
    'invalid_url',
    'not_allowed',
    'unreachable',
    'invalid_auth_name',
    'invalid_secret',
    'secret_required',
    'name_taken',
    'service_in_use',
    'service_not_found',
    'service_required',
    'variables_required',
    'unknown_variable',
    'variable_not_supported',
    'invalid_key',
    'invalid_transform',
    'invalid_path',
    'form_not_collected_here',
    'too_many_variables',
    'not_retryable',
    'registration_off',
    'forbidden',
    'not_found'
] as const;

/** What a connection test can report (`code` of the test result). */
export const TEST_CODES = ['unreachable', 'timeout', 'tls_error', 'not_allowed', 'invalid_url', 'redirect_refused', 'http_4xx', 'http_5xx', 'secret_unreadable', 'config_invalid'] as const;

/** Why a delivery failed (`lastErrorCode`). */
export const DELIVERY_ERROR_CODES = [
    'unreachable',
    'timeout',
    'tls_error',
    'not_allowed',
    'invalid_url',
    'redirect_refused',
    'http_4xx',
    'http_5xx',
    'too_large',
    'config_invalid',
    'secret_unreadable',
    'answers_unreadable',
    'file_missing',
    'disabled',
    'internal_error'
] as const;

/** Why a variable cannot be chosen (`reason`). */
export const VARIABLE_REASONS = ['not_an_answer', 'type_not_supported'] as const;

/** The code of a failed call: the API's `code`, else one from the HTTP status. */
export function errorCodeOf(error: any): string {
    const code = error?.data?.code;
    if (typeof code === 'string') return code;
    switch (error?.status) {
        case 403:
            return 'forbidden';
        case 404:
            return 'not_found';
        case 410:
            return 'registration_off';
        default:
            return 'unknown';
    }
}

const isKnown = (list: readonly string[], code: unknown): code is string => typeof code === 'string' && list.includes(code);

/** Translation key for a refusal; anything unlisted gets the generic sentence. */
export const errorKey = (code: unknown) => `REGISTRATION.ERROR.${isKnown(ERROR_CODES, code) ? code : 'unknown'}`;

/** Translation key for a test outcome (`ok` is true when it arrived). */
export const testKey = (ok: boolean, code?: string | null) => (ok ? 'REGISTRATION.TEST.ok' : `REGISTRATION.TEST.${isKnown(TEST_CODES, code) ? code : 'unknown'}`);

/** Translation key for the reason a delivery was not sent. */
export const deliveryErrorKey = (code?: string | null) => `REGISTRATION.DELIVERY.ERROR.${isKnown(DELIVERY_ERROR_CODES, code) ? code : 'unknown'}`;

/** Translation key for why a variable is greyed out. */
export const variableReasonKey = (reason?: string | null) => `REGISTRATION.FORM.REASON.${isKnown(VARIABLE_REASONS, reason) ? reason : 'type_not_supported'}`;

/** Which field of the service dialog an error belongs to, so it is shown there. */
export function serviceErrorField(code: string): 'name' | 'baseUrl' | 'authName' | 'secret' | null {
    switch (code) {
        case 'name_taken':
            return 'name';
        case 'invalid_url':
        case 'not_allowed':
        case 'unreachable':
            return 'baseUrl';
        case 'invalid_auth_name':
            return 'authName';
        case 'invalid_secret':
        case 'secret_required':
            return 'secret';
        default:
            return null;
    }
}

/** Which part of a form's registration an error belongs to. */
export function formErrorField(code: string): 'service' | 'path' | 'variables' | null {
    switch (code) {
        case 'service_required':
        case 'service_not_found':
            return 'service';
        case 'invalid_path':
            return 'path';
        case 'variables_required':
        case 'unknown_variable':
        case 'variable_not_supported':
        case 'invalid_key':
        case 'invalid_transform':
        case 'too_many_variables':
            return 'variables';
        default:
            return null;
    }
}

/** The key the API gives a variable when none is set (letters, digits and `_`). */
export const defaultKeyOf = (source: string) => source.replace(/[^A-Za-z0-9_]/g, '_');

/** A name in the sent data: starts with a letter or `_`, then letters, digits, `_`; at most 64. */
export const isValidKey = (key: string) => /^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(key);

/**
 * Changing the address, the sign-in or its name means the secret has to be
 * entered again (the API answers `secret_required` otherwise).
 */
export function needsSecretAgain(original: RegistrationService, next: { baseUrl: string; auth: RegistrationAuth; authName: string }): boolean {
    if (next.auth === 'none') return false;
    return next.baseUrl.trim() !== original.baseUrl || next.auth !== original.auth || (next.authName.trim() || '') !== (original.authName ?? '');
}

/** A variable that can be chosen. */
export const isChoosable = (variable: RegistrationVariable) => variable.supported;

/** Questions whose chosen options can be sent as a list. */
export const canBeList = (variable: RegistrationVariable) => variable.type === 'multiple_choice';

/** The deliveries that need a person's attention. */
export const ATTENTION_STATUSES = ['failed', 'cancelled'] as const;
export const WAITING_STATUSES = ['pending', 'in_progress', 'retrying'] as const;

/** A time in the reader's language, or an empty string when there is none. */
export function formatDateTime(value: string | null | undefined, language: string): string {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' });
}

/** A day in the reader's language, or an empty string when there is none. */
export function formatDay(value: string | null | undefined, language: string): string {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString(language, { dateStyle: 'medium' });
}
