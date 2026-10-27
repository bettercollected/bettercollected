/**
 * Pure helpers for the Open Formulieren import screens: the upload limits,
 * which refusal the server gave, and the report in plain words. Every string
 * the user reads lives in public/locales/<lng>/builder.json under
 * OPEN_FORMULIEREN_IMPORT and is chosen here by a stable code. Nothing the
 * server sends is ever read as markup: the screens render it as text.
 */
import type { ImportReportItem, OpenFormulierenImportRefusal } from '@app/store/redux/open-formulieren-import-api';

/** The server refuses larger uploads (api contract section 2.1). */
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MAX_UPLOAD_MB = 5;

/** Every refusal the server gives with a stable code (api contract section 3). */
export const UPLOAD_ERROR_CODES = [
    'open_formulieren_off',
    'file_missing',
    'file_too_large',
    'not_a_zip',
    'archive_unsafe',
    'archive_too_large',
    'archive_incomplete',
    'archive_json_invalid',
    'archive_not_a_single_form',
    'open_formulieren_version_unknown',
    'open_formulieren_version_unsupported',
    'no_importable_fields',
    'archive_too_complex',
    'import_busy',
    'import_limit',
    'import_not_found'
] as const;

/** The report's reason codes, stable v1 (api contract section 5). */
export const REPORT_REASONS = [
    // components
    'unsupported_component_type',
    'unknown_component_type',
    'always_hidden',
    'not_allowed_in_repeating_group',
    'converted_to_text',
    'converted_to_number',
    'converted_to_yes_no',
    'datetime_split',
    'checkbox_required_not_enforced',
    'national_identity_number',
    'multiple_not_supported',
    'choices_from_variable',
    'too_few_choices',
    'default_value_not_carried',
    'validation_not_carried',
    'file_restrictions_not_carried',
    'html_simplified',
    'custom_script_dropped',
    'prefill_not_carried',
    'date_rule_not_carried',
    'disabled_not_carried',
    'second_text_not_carried',
    'empty_step',
    'empty_group',
    'rejected_by_form_rules',
    // logic
    'trigger_not_supported',
    'action_not_supported',
    'conflicting_rules',
    'condition_source_missing',
    'condition_source_later',
    'target_missing',
    'condition_value_not_supported',
    // variables
    'user_variable_not_carried',
    // features and settings
    'sign_in_not_carried',
    'payment_not_carried',
    'appointment_not_carried',
    'registration_not_carried',
    'translations_not_carried',
    'presentation_not_carried',
    'statement_of_truth_not_carried',
    'privacy_policy_missing',
    'purpose_missing',
    'retention_global_setting',
    'retention_method_not_carried',
    'retention_other_limits_not_carried',
    'schedule_not_carried',
    'error_messages_not_carried',
    'registration_attribute_not_carried',
    // archive
    'archive_entry_ignored'
] as const;

export const REPORT_CODES = ['flagged', 'dropped', 'changed', 'noted', 'ignored'] as const;
export const NATIONAL_IDENTITY_FLAG = 'national_identity_number';

const REASONS = new Set<string>(REPORT_REASONS);
const ERROR_CODES = new Set<string>(UPLOAD_ERROR_CODES);
/** The only detail keys a sentence may use (api contract section 5). */
const DETAIL_KEYS = ['componentType', 'property', 'actionType', 'plugin', 'dataType'] as const;

/** Text from the server, made safe to put in a sentence: plain, one line, short. */
export function plainText(value: unknown, max = 80): string {
    const text = String(value ?? '')
        .replace(/[\u0000-\u001f\u007f]+/g, ' ')
        .trim();
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export interface MessageRef {
    /** Key below OPEN_FORMULIEREN_IMPORT in the builder namespace. */
    key: string;
    values: Record<string, string | number>;
}

export interface UploadProblem extends MessageRef {
    /** Why nothing was importable (422 no_importable_fields). */
    items: ImportReportItem[];
}

/** Whether a file is over what the server accepts, so we can say so before sending it. */
export function uploadTooLarge(file: { size: number }): boolean {
    return file.size > MAX_UPLOAD_BYTES;
}

/** Which message a failed request maps to, with the values it needs. */
export function uploadProblemOf(error: unknown): UploadProblem {
    const { status, data } = (error ?? {}) as { status?: number | string; data?: OpenFormulierenImportRefusal };
    const body = data && typeof data === 'object' ? data : {};
    const code = typeof body.code === 'string' ? body.code : '';
    const values: Record<string, string | number> = {};
    let items: ImportReportItem[] = [];

    if (!ERROR_CODES.has(code)) {
        // a member without the form-create permission gets the workspace's own 403
        return { key: status === 403 ? 'ERROR.forbidden' : 'ERROR.upload_failed', values, items };
    }
    if (code === 'file_too_large') {
        const bytes = Number(body.maxBytes);
        values.mb = Number.isFinite(bytes) && bytes > 0 ? Math.max(1, Math.floor(bytes / 1024 / 1024)) : MAX_UPLOAD_MB;
    }
    if (code === 'archive_incomplete') {
        values.files = (Array.isArray(body.missing) ? body.missing : [])
            .slice(0, 6)
            .map((name) => plainText(name, 60))
            .filter(Boolean)
            .join(', ');
    }
    if (code === 'archive_json_invalid') {
        values.file = plainText(body.file, 60);
        // `file: "archive"` is not a file name: something in the zip could not be read
        if (values.file === 'archive' || !values.file) return { key: 'ERROR.archive_unreadable', values: {}, items };
    }
    if (code === 'open_formulieren_version_unsupported') {
        values.version = plainText(body.version, 40);
        // "4.0" is a series: name it as the exports it reads ("4.0.x")
        values.supported = (Array.isArray(body.supported) ? body.supported : [])
            .slice(0, 6)
            .map((series) => plainText(series, 20))
            .filter(Boolean)
            .map((series) => (/^\d+\.\d+$/.test(series) ? `${series}.x` : series))
            .join(', ');
    }
    if (code === 'no_importable_fields' && Array.isArray(body.reportItems)) items = body.reportItems.filter((item) => item && typeof item === 'object').slice(0, 50);
    return { key: `ERROR.${code}`, values, items };
}

/**
 * The sentence for one report item, from its reason and detail. An unknown
 * reason (a newer server) gets a generic line for what happened to it.
 */
export function reportSentenceOf(item: Pick<ImportReportItem, 'code' | 'reason' | 'key' | 'detail'>): MessageRef {
    const values: Record<string, string | number> = {};
    for (const name of DETAIL_KEYS) {
        const value = item.detail?.[name];
        if (value !== undefined && value !== null && typeof value !== 'object') values[name] = plainText(value);
    }
    if (item.key) values.key = plainText(item.key, 120);
    if (REASONS.has(item.reason)) return { key: `REASON.${item.reason}`, values };
    const code = (REPORT_CODES as ReadonlyArray<string>).includes(item.code) ? item.code : 'other';
    return { key: `REASON_FALLBACK.${code}`, values };
}

/**
 * The label of an item as a line to read: its label, else the key of a
 * question or variable (a name the creator knows). The key of a setting,
 * feature, rule or file is an internal identifier, so it is not shown.
 */
export function reportLabelOf(item: Pick<ImportReportItem, 'label' | 'key' | 'kind'>): string {
    if (item.label) return plainText(item.label, 200);
    return item.kind === 'component' || item.kind === 'variable' ? plainText(item.key, 200) : '';
}

export interface ReportGroup {
    code: (typeof REPORT_CODES)[number] | 'other';
    items: ImportReportItem[];
}

const KIND_RANK: Record<string, number> = { component: 0, logic: 1, variable: 2, feature: 3, setting: 4, archive: 5 };

/**
 * Items grouped by what happened to them, the ones to check first. Inside a
 * group: questions page by page, then rules, variables, features, settings and
 * files; items that tie keep the server's order (the contract does not promise one).
 */
export function groupReport(items: ReadonlyArray<ImportReportItem>): ReportGroup[] {
    const groups: ReportGroup[] = [...REPORT_CODES, 'other'].map((code) => ({ code, items: [] }) as ReportGroup);
    for (const item of items ?? []) {
        if (!item || typeof item !== 'object') continue;
        const group = groups.find((g) => g.code === item.code) ?? groups[groups.length - 1];
        group.items.push(item);
    }
    const rank = (item: ImportReportItem) => KIND_RANK[item.kind] ?? 6;
    const page = (item: ImportReportItem) => (typeof item.step === 'number' ? item.step : 0);
    for (const group of groups) group.items.sort((a, b) => rank(a) - rank(b) || (rank(a) === 0 ? page(a) - page(b) : 0));
    return groups.filter((group) => group.items.length > 0);
}

export function nationalIdentityItems(items: ReadonlyArray<ImportReportItem>): ImportReportItem[] {
    return (items ?? []).filter((item) => item && (item.flag === NATIONAL_IDENTITY_FLAG || item.reason === NATIONAL_IDENTITY_FLAG));
}
