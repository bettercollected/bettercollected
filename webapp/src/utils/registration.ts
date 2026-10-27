import type { RegistrationAuth, RegistrationKind, RegistrationService, RegistrationVariable } from '@app/store/workspaces/registration-api';

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
    'invalid_auth',
    'objecttypes_base_required',
    'objecttypes_base_not_applicable',
    'invalid_object_type_url',
    'object_type_outside_base',
    'invalid_object_type_version',
    'object_type_required',
    'invalid_target_path',
    'target_path_conflict',
    'invalid_reference_path',
    'reference_path_conflict',
    'not_an_objects_api',
    'rate_limited',
    'not_retryable',
    'registration_off',
    'forbidden',
    'not_found'
] as const;

/** What a connection test can report (`code` of the test result). */
export const TEST_CODES = ['use_form_check', 'unreachable', 'timeout', 'tls_error', 'not_allowed', 'invalid_url', 'redirect_refused', 'http_4xx', 'http_5xx', 'secret_unreadable', 'config_invalid'] as const;

/** What a form's "Check connection" can report (Objects API). */
export const CHECK_CODES = ['not_configured', 'lookup_failed', 'filter_not_supported', 'secret_unreadable', 'config_invalid', 'unreachable', 'timeout', 'tls_error', 'not_allowed', 'invalid_url', 'redirect_refused', 'http_5xx', 'rate_limited'] as const;

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
    'lookup_failed',
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
        case 429:
            return 'rate_limited';
        default:
            return 'unknown';
    }
}

const isKnown = (list: readonly string[], code: unknown): code is string => typeof code === 'string' && list.includes(code);

/** Translation key for a refusal; anything unlisted gets the generic sentence. */
export const errorKey = (code: unknown) => `REGISTRATION.ERROR.${isKnown(ERROR_CODES, code) ? code : 'unknown'}`;

/** Translation key for a test outcome (`ok` is true when it arrived). */
export const testKey = (ok: boolean, code?: string | null) => (ok ? 'REGISTRATION.TEST.ok' : `REGISTRATION.TEST.${isKnown(TEST_CODES, code) ? code : 'unknown'}`);

/** Translation key for the outcome of a form's "Check connection". */
export const checkKey = (ok: boolean, code?: string | null) => (ok ? 'REGISTRATION.CHECK.ok' : `REGISTRATION.CHECK.${isKnown(CHECK_CODES, code) ? code : 'unknown'}`);

/**
 * Translation key for the reason a delivery was not sent. An Objects API
 * refusal with status 400 is the object type not accepting the data (a
 * mismatch between the mapping and its schema), and 401/403 is the token being
 * refused: each gets its own sentence.
 */
export function deliveryErrorKey(code?: string | null, options: { objectsApi?: boolean; httpStatus?: number | null } = {}): string {
    if (code === 'http_4xx' && options.objectsApi && options.httpStatus === 400) return 'REGISTRATION.DELIVERY.ERROR.http_4xx_schema';
    if (code === 'http_4xx' && options.objectsApi && (options.httpStatus === 401 || options.httpStatus === 403)) return 'REGISTRATION.DELIVERY.ERROR.http_4xx_token';
    return `REGISTRATION.DELIVERY.ERROR.${isKnown(DELIVERY_ERROR_CODES, code) ? code : 'unknown'}`;
}

/** Translation key for why a variable is greyed out. */
export const variableReasonKey = (reason?: string | null) => `REGISTRATION.FORM.REASON.${isKnown(VARIABLE_REASONS, reason) ? reason : 'type_not_supported'}`;

/** Which field of the service dialog an error belongs to, so it is shown there. */
export function serviceErrorField(code: string, kind: RegistrationKind = 'generic_json'): 'name' | 'baseUrl' | 'objecttypesBaseUrl' | 'authName' | 'secret' | null {
    switch (code) {
        case 'name_taken':
            return 'name';
        case 'objecttypes_base_required':
            return 'objecttypesBaseUrl';
        case 'invalid_url':
        case 'not_allowed':
        case 'unreachable':
            // The API does not say which of the two addresses it refused.
            return kind === 'objects_api' ? null : 'baseUrl';
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
export function formErrorField(code: string): 'service' | 'path' | 'variables' | 'objectType' | 'version' | 'reference' | null {
    switch (code) {
        case 'service_required':
        case 'service_not_found':
        case 'not_an_objects_api':
            return 'service';
        case 'invalid_object_type_url':
        case 'object_type_outside_base':
        case 'object_type_required':
            return 'objectType';
        case 'invalid_object_type_version':
            return 'version';
        case 'invalid_reference_path':
        case 'reference_path_conflict':
            return 'reference';
        case 'invalid_target_path':
        case 'target_path_conflict':
            return 'variables';
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
    // The Objects API token goes with the address it is sent to; the object
    // types address is never connected to, so changing it keeps the token.
    if (original.kind === 'objects_api') return next.baseUrl.trim() !== original.baseUrl;
    return next.baseUrl.trim() !== original.baseUrl || next.auth !== original.auth || (next.authName.trim() || '') !== (original.authName ?? '');
}

/**
 * A path that can be added to a service address: relative, plain characters, no `..`
 * (also once or twice encoded), query, fragment, backslash or scheme. Mirrors the
 * server's rule so a switch-off never carries a path it would refuse; the server decides.
 */
export function isPlainPath(path: string): boolean {
    if (path.length > 255 || !/^[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$/.test(path) || path.startsWith('//') || /^[A-Za-z][A-Za-z0-9+.-]*:/.test(path)) return false;
    // Like the server's unquote: valid %XX escapes are decoded, a lone % stays as it is.
    const unquote = (text: string) => text.replace(/%([0-9A-Fa-f]{2})/g, (_match, hex: string) => String.fromCharCode(parseInt(hex, 16)));
    return !/\.\.|\\|\?|#/.test(unquote(unquote(path)));
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

// --- Objects API ---------------------------------------------------------------

/** Where our delivery reference goes in the object's data unless set otherwise. */
export const DEFAULT_REFERENCE_PATH = 'bettercollected_reference';
export const MAX_TARGET_DEPTH = 8;
/** The most variables a form's registration holds (the server refuses more). */
export const MAX_VARIABLES = 200;
export const OBJECT_TYPE_URL_MAX = 1000;
/** The token has no whitespace and is plain ASCII; the server is authoritative. */
export const isPlainToken = (token: string) => token.length > 0 && /^[\x21-\x7E]+$/.test(token);

/** One name of a path: a letter first, then letters, digits and `_`; no `__`, no trailing `_`; at most 64. */
export const isValidSegment = (segment: string) => /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(segment) && !segment.includes('__') && !segment.endsWith('_');

/** `a.b.c` into `['a','b','c']`; null when a name breaks the rules or there are none or too many. */
export function parseTargetPath(text: string): string[] | null {
    const trimmed = text.trim();
    if (!trimmed) return null;
    const segments = trimmed.split('.').map((segment) => segment.trim());
    if (segments.length > MAX_TARGET_DEPTH || !segments.every(isValidSegment)) return null;
    return segments;
}

/** `['a','b','c']` into `a.b.c`. */
export const formatTargetPath = (path?: string[] | null) => (path ?? []).join('.');

const isPrefix = (shorter: string[], longer: string[]) => shorter.length <= longer.length && shorter.every((segment, index) => segment === longer[index]);

/** The first two target paths that are the same or one inside the other; the second is the later one. */
export function findTargetConflict(paths: Array<{ source: string; path: string[] }>): { first: string; second: string } | null {
    for (let i = 0; i < paths.length; i += 1) {
        for (let j = i + 1; j < paths.length; j += 1) {
            if (isPrefix(paths[i].path, paths[j].path) || isPrefix(paths[j].path, paths[i].path)) return { first: paths[i].source, second: paths[j].source };
        }
    }
    return null;
}

/** The reference path must not equal, contain or sit inside a mapped path. */
export const referenceConflicts = (reference: string[], mapped: string[][]) => mapped.some((path) => isPrefix(reference, path) || isPrefix(path, reference));

/**
 * A form's object type address: https, at most 1000 characters, no user
 * name, port, query or fragment, ending `/objecttypes/<uuid>`, plain path
 * names only. The address is checked as text and never fetched. Returns the
 * refusal's code (as the API words it) or null.
 */
export function objectTypeUrlProblem(value: string, objecttypesBaseUrl?: string | null): 'invalid_object_type_url' | 'object_type_outside_base' | null {
    const text = value.trim();
    if (!text || text.length > OBJECT_TYPE_URL_MAX) return 'invalid_object_type_url';
    const match = /^https:\/\/([^/?#@:\\\s]+)(\/[^?#\s]*)$/i.exec(text);
    if (!match) return 'invalid_object_type_url';
    const segments = match[2].split('/').slice(1);
    if (segments.some((segment) => !segment || segment === '.' || segment === '..' || /[%;\\]/.test(segment))) return 'invalid_object_type_url';
    const [kind, id] = segments.slice(-2);
    if (segments.length < 2 || kind.toLowerCase() !== 'objecttypes' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) return 'invalid_object_type_url';
    if (objecttypesBaseUrl) {
        const base = /^https:\/\/([^/?#]+)(\/[^?#]*)?/i.exec(objecttypesBaseUrl.trim());
        if (base) {
            const basePath = (base[2] ?? '').replace(/\/+$/, '').toLowerCase();
            const path = match[2].toLowerCase();
            const inside = path === basePath || path.startsWith(`${basePath}/`);
            if (match[1].toLowerCase() !== base[1].toLowerCase() || !inside) return 'object_type_outside_base';
        }
    }
    return null;
}

/** The version of an object type: a whole number from 1 to 10000. */
export const isValidObjectTypeVersion = (value: string) => /^[0-9]{1,5}$/.test(value.trim()) && Number(value) >= 1 && Number(value) <= 10000;
