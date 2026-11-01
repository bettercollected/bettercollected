import type { TFunction } from 'i18next';

import type { VersionChange } from '@app/store/workspaces/form-versions-api';

/**
 * Words for the coded changes of two form versions (backend
 * `services/form_versions/compare.py`): the server says what kind of change it
 * saw, this says it in the viewer's language. The values in `params` are the
 * form's own content (titles, option labels), shown as text, never markup.
 */

const UNTITLED = 'FORM_VERSIONS.CHANGE.UNTITLED_QUESTION';

/** "Short text", "Dropdown", ...: the name of a question type, the raw type when there is none. */
export function questionTypeName(t: TFunction, type: unknown): string {
    const raw = String(type ?? '');
    // the builder's names for the types it lists, ours for the few it does not, else the raw type
    return t(`REGISTRATION.FORM.TYPE.${raw}`, { ns: 'builder', defaultValue: t(`FORM_VERSIONS.TYPE.${raw}`, { defaultValue: raw }) });
}

/** What a changed spec key is called, for the "something else changed" sentences. */
export function keyName(t: TFunction, key: string): string {
    return t(`FORM_VERSIONS.KEY.${key}`, { defaultValue: key });
}

function keyList(t: TFunction, keys: unknown): string {
    return (Array.isArray(keys) ? keys : []).map((key) => keyName(t, String(key))).join(', ');
}

function quoted(text: unknown): string {
    return `“${String(text ?? '')}”`;
}

function question(t: TFunction, change: VersionChange): string {
    return change.title ? quoted(change.title) : t(UNTITLED);
}

function page(t: TFunction, change: VersionChange): string {
    const label = t('FORM_VERSIONS.CHANGE.PAGE_N', { number: change.params.number ?? change.params.after ?? '' });
    return change.title ? `${label} (${quoted(change.title)})` : label;
}

/** One sentence for one change. An unknown kind is shown as its code, so nothing is hidden. */
export function describeChange(t: TFunction, change: VersionChange): string {
    const p = change.params ?? {};
    const key = `FORM_VERSIONS.CHANGE.${change.kind}`;
    switch (change.kind) {
        case 'form_title_changed':
            return t(key, { before: p.before || t('FORM_VERSIONS.CHANGE.NO_TITLE'), after: p.after || t('FORM_VERSIONS.CHANGE.NO_TITLE') });
        case 'language_changed':
            return t(key, { before: String(p.before ?? '-').toUpperCase(), after: String(p.after ?? '-').toUpperCase() });
        case 'hidden_fields_added':
        case 'hidden_fields_removed':
            return t(key, { names: (Array.isArray(p.names) ? p.names : []).join(', ') });
        case 'page_added':
        case 'page_removed':
        case 'page_jumps_changed':
            return t(key, { page: page(t, change) });
        case 'page_moved':
            return t(key, { page: page(t, { ...change, params: { number: p.after } }), before: p.before, after: p.after });
        case 'page_changed':
            return t(key, { page: page(t, change), keys: keyList(t, p.keys) });
        case 'question_added':
        case 'question_removed':
            return t(typeof p.page === 'number' ? `${key}_ON_PAGE` : key, { question: question(t, change), type: questionTypeName(t, p.type), page: p.page });
        case 'question_moved':
            return t(typeof p.before === 'number' && typeof p.after === 'number' ? key : `${key}_PLAIN`, { question: question(t, change), before: p.before, after: p.after });
        case 'title_changed':
            return t(key, { before: quoted(p.before || t(UNTITLED)), after: quoted(p.after || t(UNTITLED)) });
        case 'type_changed':
            return t(key, { question: question(t, change), before: questionTypeName(t, p.before), after: questionTypeName(t, p.after) });
        case 'required_changed':
            return t(p.required ? `${key}_ON` : `${key}_OFF`, { question: question(t, change) });
        case 'choice_added':
        case 'choice_removed':
        case 'choice_logic_changed':
            return t(key, { question: question(t, change), value: quoted(p.value) });
        case 'choice_renamed':
            return t(key, { question: question(t, change), before: quoted(p.before), after: quoted(p.after) });
        case 'rules_changed': {
            const parts = (['added', 'removed', 'changed'] as const)
                .filter((part) => Number(p[part]) > 0)
                .map((part) => t(`FORM_VERSIONS.CHANGE.RULES_${part.toUpperCase()}`, { count: Number(p[part]) }));
            return t(key, { question: question(t, change), summary: parts.join(', ') });
        }
        case 'validation_changed':
        case 'other_changed':
            return t(change.scope === 'form' ? `${key}_FORM` : key, { question: question(t, change), keys: keyList(t, p.keys) });
        case 'form_description_changed':
        case 'theme_changed':
        case 'welcome_page_changed':
        case 'ending_changed':
        case 'logo_settings_changed':
        case 'choices_reordered':
        case 'rules_reordered':
        case 'logic_changed':
        case 'calculation_changed':
        case 'description_changed':
            return t(key, { question: question(t, change) });
        default:
            return change.kind;
    }
}

export interface ChangeGroup {
    scope: 'form' | 'page' | 'question';
    changes: VersionChange[];
}

/** The changes under three headings (the form, its pages, its questions), empty ones left out. */
export function groupChanges(entries: VersionChange[]): ChangeGroup[] {
    return (['form', 'page', 'question'] as const).map((scope) => ({ scope, changes: entries.filter((entry) => entry.scope === scope) })).filter((group) => group.changes.length > 0);
}
