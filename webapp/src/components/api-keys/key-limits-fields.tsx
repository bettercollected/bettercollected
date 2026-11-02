'use client';

import { useEffect, useId, useMemo, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { CardRestrictedChip } from '@app/components/form/access/restricted-chip';
import { Button } from '@app/shadcn/components/ui/button';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import { KEY_ROLE_OPTIONS, KeyFormScope, KeyRole, MAX_KEY_FORMS, lowestRoleFor, scopeProblems } from './key-rules';

// the most the forms list sends in one page
const FORMS_PAGE_SIZE = 100;

export type KnownForm = { id: string; title?: string | null };

// the scope's label, as the page lists them
const SCOPE_LABELS: Record<string, string> = {
    'forms:read': 'STAFF.API_KEYS.SCOPE_FORMS_READ',
    'forms:write': 'STAFF.API_KEYS.SCOPE_FORMS_WRITE',
    'forms:delete': 'STAFF.API_KEYS.SCOPE_FORMS_DELETE',
    'responses:read': 'STAFF.API_KEYS.SCOPE_RESPONSES_READ',
    'deletion_requests:read': 'STAFF.API_KEYS.SCOPE_DELETIONS_READ',
    'deletion_requests:write': 'STAFF.API_KEYS.SCOPE_DELETIONS_WRITE',
    'submissions:write': 'STAFF.API_KEYS.SCOPE_SUBMISSIONS_WRITE'
};
export const scopeLabelKey = (scope: string) => SCOPE_LABELS[scope] ?? scope;

export const roleNameKey = (role: KeyRole) => `WORKSPACE_ROLES.${role}.NAME`;

const rowClass = 'flex min-h-11 cursor-pointer items-center gap-2.5 rounded px-1 text-[13px] text-black-800 sm:min-h-8';
const fieldClass = 'border-control text-black-900 placeholder:text-black-600 focus:border-brand-500 h-11 w-full rounded-md border bg-white px-3.5 text-sm outline-hidden transition duration-150 sm:h-10';

/**
 * Why the scopes ticked cannot go with the role or the list chosen, one line each, in plain words. An alert region
 * so a screen reader hears it when it appears; empty (and not rendered) when the combination is one the server takes.
 */
export function ScopeProblems({ role, formScope, scopes, id }: { role: KeyRole | null; formScope: KeyFormScope; scopes: string[]; id?: string }) {
    const { t } = useTranslation();
    const problems = scopeProblems(role, formScope, scopes);
    if (problems.length === 0) return null;
    return (
        <div id={id} role="alert" className="flex flex-col gap-1 rounded-md border border-[#E8C4C4] bg-[#FBEFEF] p-3 text-xs text-[#8F2C2C]">
            {problems.map(({ scope, reason }) => (
                <p key={scope}>{t(reason === 'list' ? 'STAFF.API_KEYS.ERR_NOT_ALLOWED_LISTED' : 'STAFF.API_KEYS.ERR_NOT_ALLOWED', { scope: t(scopeLabelKey(scope)) })}</p>
            ))}
        </div>
    );
}

/**
 * The picker of the forms a key may open: every form the person setting it may open (drafts and restricted forms
 * too, with chips), a search over what is loaded, "select all shown", and at most MAX_KEY_FORMS. Asked for only
 * while it is on screen, so a key that is not limited to a list makes no request. Forms already on the key are
 * always listed, whether or not their page has been loaded, so each can be taken off again.
 */
function FormPicker({ formIds, onChange, knownForms }: { formIds: string[]; onChange: (ids: string[]) => void; knownForms: KnownForm[] }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const searchId = useId();
    const [page, setPage] = useState(1);
    const [pages, setPages] = useState<Record<number, any[]>>({});
    const [search, setSearch] = useState('');
    const { data, isLoading } = useGetWorkspaceFormsQuery({ workspace_id: workspace?.id, page, size: FORMS_PAGE_SIZE }, { skip: !workspace?.id });
    useEffect(() => {
        const loaded = data as any;
        if (loaded) setPages((current) => ({ ...current, [loaded.page ?? page]: loaded.items ?? [] }));
    }, [data]);

    const loaded = useMemo(
        () =>
            Object.keys(pages)
                .map(Number)
                .sort((a, b) => a - b)
                .flatMap((number) => pages[number])
                .filter((form, index, all) => all.findIndex((other) => other.formId === form.formId) === index),
        [pages]
    );
    // the forms on the key that no loaded page has (yet), by what the key's list said of them
    const choices: Array<{ formId: string; title?: string | null; form?: any }> = useMemo(() => {
        const rest = formIds.filter((id) => !loaded.some((form) => form.formId === id)).map((id) => ({ formId: id, title: knownForms.find((known) => known.id === id)?.title }));
        return [...loaded.map((form) => ({ formId: form.formId, title: form.title, form })), ...rest];
    }, [loaded, formIds, knownForms]);
    const wanted = search.trim().toLowerCase();
    const shown = wanted ? choices.filter((form) => (form.title ?? '').toLowerCase().includes(wanted)) : choices;
    const more = ((data as any)?.pages ?? 1) > page;
    const full = formIds.length >= MAX_KEY_FORMS;
    const toggle = (id: string) => onChange(formIds.includes(id) ? formIds.filter((other) => other !== id) : full ? formIds : [...formIds, id]);
    const selectShown = () => onChange([...new Set([...formIds, ...shown.map((form) => form.formId)])].slice(0, MAX_KEY_FORMS));

    return (
        <div className="flex flex-col gap-2 pl-0 sm:pl-6">
            <div className="flex flex-col gap-1">
                <label htmlFor={searchId} className="text-xs font-medium text-black-800">
                    {t('STAFF.API_KEYS.PICKER_SEARCH')}
                </label>
                <input id={searchId} type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('STAFF.API_KEYS.PICKER_SEARCH_PLACEHOLDER')} className={fieldClass} />
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <p role="status" className="text-xs text-black-700">
                    {t('STAFF.API_KEYS.PICKER_COUNT', { count: formIds.length, max: MAX_KEY_FORMS })}
                </p>
                <Button type="button" size="sm" variant="v2GhostButton" className="min-h-11 sm:min-h-0" disabled={shown.length === 0 || full} onClick={selectShown}>
                    {t('STAFF.API_KEYS.PICKER_SELECT_SHOWN')}
                </Button>
                <Button type="button" size="sm" variant="v2GhostButton" className="min-h-11 sm:min-h-0" disabled={formIds.length === 0} onClick={() => onChange([])}>
                    {t('STAFF.API_KEYS.PICKER_CLEAR')}
                </Button>
            </div>
            {full && <p className="text-xs text-black-700">{t('STAFF.API_KEYS.PICKER_MAX', { max: MAX_KEY_FORMS })}</p>}
            {isLoading && choices.length === 0 ? (
                <p className="text-xs text-black-600">{t('STAFF.COMMON.LOADING')}</p>
            ) : choices.length === 0 ? (
                <p className="text-xs text-black-600">{t('STAFF.API_KEYS.PICKER_EMPTY')}</p>
            ) : shown.length === 0 ? (
                <p className="text-xs text-black-600">{t('STAFF.API_KEYS.PICKER_NONE_MATCH')}</p>
            ) : (
                <ul className="flex max-h-64 flex-col overflow-y-auto rounded-md border border-black-300 p-1" aria-label={t('STAFF.API_KEYS.FORMS_TITLE')}>
                    {shown.map((form) => {
                        const checked = formIds.includes(form.formId);
                        return (
                            <li key={form.formId}>
                                <label className={rowClass}>
                                    <input type="checkbox" checked={checked} disabled={!checked && full} onChange={() => toggle(form.formId)} className="h-4 w-4 shrink-0 cursor-pointer" />
                                    <span className="min-w-0 truncate">{form.title?.trim() || (form.form ? t('STAFF.API_KEYS.UNTITLED_FORM') : t('STAFF.API_KEYS.UNKNOWN_FORM'))}</span>
                                    {form.form && !form.form.isPublished && <span className="shrink-0 rounded bg-black-100 px-1.5 py-0.5 text-[10.5px] font-semibold text-black-600">{t('FORM.DRAFT')}</span>}
                                    {form.form && <CardRestrictedChip form={form.form} />}
                                </label>
                            </li>
                        );
                    })}
                </ul>
            )}
            {more && (
                <div>
                    <Button type="button" size="sm" variant="v2GhostButton" className="min-h-11 sm:min-h-0" onClick={() => setPage((current) => current + 1)}>
                        {t('STAFF.API_KEYS.MORE_FORMS')}
                    </Button>
                </div>
            )}
        </div>
    );
}

export interface KeyLimitsFieldsProps {
    /** The scopes of the key (ticked in the create form, the key's own in the edit dialog). */
    scopes: string[];
    role: KeyRole | null;
    /** While true (a new key whose role nobody has chosen), the role follows the scopes: the lowest that allows them. */
    roleFollowsScopes?: boolean;
    onRoleChange: (role: KeyRole | null) => void;
    formScope: KeyFormScope;
    onFormScopeChange: (formScope: KeyFormScope) => void;
    formIds: string[];
    onFormIdsChange: (ids: string[]) => void;
    /** Titles the key's own list carries, for forms the picker has not loaded. */
    knownForms?: KnownForm[];
    /** Where the radios of this instance get their group name (a page may hold two). */
    idPrefix: string;
    /** The scope problems are shown by the caller (for instance below the scope boxes). */
    hideScopeProblems?: boolean;
}

/**
 * The role and form scope of an API key: what the create form and the edit dialog share (shown only while the
 * server has key roles on, `apiKeyRolesEnabled`). Controls are labelled, the role select and the two radios are
 * native, rows are 44 px tall on a phone, and a combination the server would refuse is explained here first.
 */
export default function KeyLimitsFields({ scopes, role, roleFollowsScopes = false, onRoleChange, formScope, onFormScopeChange, formIds, onFormIdsChange, knownForms = [], idPrefix, hideScopeProblems }: KeyLimitsFieldsProps) {
    const { t } = useTranslation();
    const listed = formScope === 'listed';
    const suggested = lowestRoleFor(scopes);
    const shownRole = roleFollowsScopes ? suggested : role;
    const roleId = `${idPrefix}-role`;
    const roleHelpId = `${idPrefix}-role-help`;

    return (
        <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
                <label htmlFor={roleId} className="text-[13px] font-semibold text-black-900">
                    {t('STAFF.API_KEYS.ROLE_TITLE')}
                </label>
                <select id={roleId} aria-describedby={roleHelpId} value={shownRole ?? ''} onChange={(event) => onRoleChange((event.target.value || null) as KeyRole | null)} className={`${fieldClass} pr-8`}>
                    <option value="">{t('STAFF.API_KEYS.ROLE_CREATOR')}</option>
                    {KEY_ROLE_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                            {t(roleNameKey(option))}
                        </option>
                    ))}
                </select>
                <p id={roleHelpId} className="max-w-[62ch] text-xs leading-relaxed text-black-600">
                    {t('STAFF.API_KEYS.ROLE_HELP')}
                    {roleFollowsScopes && <span className="block">{suggested ? `${t(roleNameKey(suggested))}: ${t('STAFF.API_KEYS.ROLE_SUGGESTED')}` : t('STAFF.API_KEYS.ROLE_NO_SUGGESTION')}</span>}
                </p>
            </div>

            <fieldset className="flex flex-col gap-1">
                <legend className="mb-1 text-[13px] font-semibold text-black-900">{t('STAFF.API_KEYS.FORMS_TITLE')}</legend>
                <label className={rowClass}>
                    <input type="radio" name={`${idPrefix}-forms`} checked={!listed} onChange={() => onFormScopeChange('all')} className="h-4 w-4 shrink-0 cursor-pointer" />
                    <span>{t('STAFF.API_KEYS.FORMS_ALL')}</span>
                </label>
                <label className={rowClass}>
                    <input type="radio" name={`${idPrefix}-forms`} checked={listed} onChange={() => onFormScopeChange('listed')} className="h-4 w-4 shrink-0 cursor-pointer" />
                    <span>{t('STAFF.API_KEYS.FORMS_LISTED')}</span>
                </label>
                {listed && <p className="max-w-[62ch] pl-0 text-xs leading-relaxed text-black-600 sm:pl-6">{t('STAFF.API_KEYS.FORMS_LISTED_NOTE')}</p>}
            </fieldset>
            {listed && <FormPicker formIds={formIds} onChange={onFormIdsChange} knownForms={knownForms} />}

            {!hideScopeProblems && <ScopeProblems role={shownRole} formScope={formScope} scopes={scopes} />}

            <p className="max-w-[62ch] text-xs leading-relaxed text-black-700">{!listed ? t('STAFF.API_KEYS.SUMMARY_ALL') : formIds.length === 0 ? t('STAFF.API_KEYS.SUMMARY_LISTED_NONE') : t('STAFF.API_KEYS.SUMMARY_LISTED', { count: formIds.length })}</p>
        </div>
    );
}
