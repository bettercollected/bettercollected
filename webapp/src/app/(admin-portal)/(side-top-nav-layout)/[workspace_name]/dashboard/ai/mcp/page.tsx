'use client';

import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Check, Copy, KeyRound } from 'lucide-react';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';

import environments from '@app/configs/environments';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useAppSelector } from '@app/store/hooks';
import { useCreateAPIKeyMutation, useGetAPIKeysQuery, useGetWorkspaceFormsQuery, useRevokeAPIKeyMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { APIKey, keyFormScopeOf, keyRoleOf } from '@app/components/api-keys/api-key';
import EditKeyDialog from '@app/components/api-keys/edit-key-dialog';
import { errorText, keyErrorText } from '@app/components/api-keys/key-errors';
import KeyLimitsFields, { ScopeProblems, roleNameKey } from '@app/components/api-keys/key-limits-fields';
import { KeyFormScope, KeyRole, listAllowsScope, lowestRoleFor, roleAllowsScope, scopeProblems } from '@app/components/api-keys/key-rules';

// the most the forms list sends in one page
const FORMS_PAGE_SIZE = 100;

// Mirrors the backend's VALID_SCOPES — what a key is allowed to do.
const SCOPES: Array<{ key: string; label: string; hint: string }> = [
    { key: 'forms:read', label: 'STAFF.API_KEYS.SCOPE_FORMS_READ', hint: 'STAFF.API_KEYS.SCOPE_FORMS_READ_HINT' },
    { key: 'forms:write', label: 'STAFF.API_KEYS.SCOPE_FORMS_WRITE', hint: 'STAFF.API_KEYS.SCOPE_FORMS_WRITE_HINT' },
    { key: 'forms:delete', label: 'STAFF.API_KEYS.SCOPE_FORMS_DELETE', hint: 'STAFF.API_KEYS.SCOPE_FORMS_DELETE_HINT' },
    { key: 'responses:read', label: 'STAFF.API_KEYS.SCOPE_RESPONSES_READ', hint: 'STAFF.API_KEYS.SCOPE_RESPONSES_READ_HINT' },
    { key: 'deletion_requests:read', label: 'STAFF.API_KEYS.SCOPE_DELETIONS_READ', hint: 'STAFF.API_KEYS.SCOPE_DELETIONS_READ_HINT' },
    { key: 'deletion_requests:write', label: 'STAFF.API_KEYS.SCOPE_DELETIONS_WRITE', hint: 'STAFF.API_KEYS.SCOPE_DELETIONS_WRITE_HINT' }
];

// Offered only while the server accepts it (its SUBMISSIONS_API_ENABLED, told with the permissions).
const SUBMISSIONS_SCOPE = { key: 'submissions:write', label: 'STAFF.API_KEYS.SCOPE_SUBMISSIONS_WRITE', hint: 'STAFF.API_KEYS.SCOPE_SUBMISSIONS_WRITE_HINT' };

function CopyButton({ value, label }: { value: string; label: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <button
            type="button"
            aria-label={label}
            onClick={async () => {
                await navigator.clipboard.writeText(value);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
            }}
            className="text-black-600 hover:text-black-800 shrink-0 rounded p-1 transition-colors"
        >
            {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
        </button>
    );
}

/**
 * The MCP tab of the AI section: the MCP endpoint and the workspace API keys,
 * the credentials external AI tools (Claude, ChatGPT, anything MCP-capable),
 * the public REST API and the SDKs use to work with this workspace.
 * The token is shown exactly once at creation; only its prefix is kept.
 */
export default function APIKeysPage() {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const workspace = useAppSelector(selectWorkspace);
    const { can, submissionsApiEnabled, apiKeyRolesEnabled } = useWorkspacePermissions();
    const canManageKeys = can(WorkspacePermission.SECURITY_MANAGE);
    const { toast } = useToast();

    const { data: keys = [], isLoading, refetch } = useGetAPIKeysQuery(workspace?.id, { skip: !workspace?.id || !canManageKeys });
    const [createKey, { isLoading: isCreating }] = useCreateAPIKeyMutation();
    const [revokeKey] = useRevokeAPIKeyMutation();

    const [name, setName] = useState('');
    const [scopes, setScopes] = useState<string[]>(['forms:read']);
    // responses:read hands full, unredacted answers to the AI client (#715)
    const [acknowledged, setAcknowledged] = useState(false);
    const readsResponses = scopes.includes('responses:read');
    // the server turned the feature off while the dialog was open: the scope can no longer be given
    useEffect(() => {
        if (!submissionsApiEnabled) setScopes((current) => (current.includes('submissions:write') ? current.filter((scope) => scope !== 'submissions:write') : current));
    }, [submissionsApiEnabled]);
    // submissions:write may be limited to some of the workspace's published forms (none picked: every form)
    const submits = scopes.includes(SUBMISSIONS_SCOPE.key);
    const [limitForms, setLimitForms] = useState(false);
    const [formIds, setFormIds] = useState<string[]>([]);
    // the picker pages through every published form, FORMS_PAGE_SIZE at a time (the API's largest page)
    const [formsPage, setFormsPage] = useState(1);
    const [formPages, setFormPages] = useState<Record<number, Array<{ formId: string; title?: string }>>>({});
    const { data: publishedForms } = useGetWorkspaceFormsQuery({ workspace_id: workspace?.id, published: true, page: formsPage, size: FORMS_PAGE_SIZE }, { skip: !workspace?.id || !submits || !submissionsApiEnabled });
    useEffect(() => {
        const loaded = publishedForms as any;
        if (loaded) setFormPages((current) => ({ ...current, [loaded.page ?? formsPage]: loaded.items ?? [] }));
    }, [publishedForms]);
    const formChoices = Object.keys(formPages)
        .map(Number)
        .sort((a, b) => a - b)
        .flatMap((page) => formPages[page])
        .filter((form, index, all) => all.findIndex((other) => other.formId === form.formId) === index);
    const moreForms = ((publishedForms as any)?.pages ?? 1) > formsPage;
    const scopeChoices = submissionsApiEnabled ? [...SCOPES, SUBMISSIONS_SCOPE] : SCOPES;

    // Key roles (apiKeyRolesEnabled): the most the key may do and the forms it may open. A new key's role follows the
    // scopes ticked (the lowest role that allows them) until somebody picks one; nothing here exists while the switch is off.
    const [role, setRole] = useState<KeyRole | null>(null);
    const [roleChosen, setRoleChosen] = useState(false);
    const [formScope, setFormScope] = useState<KeyFormScope>('all');
    const [listedIds, setListedIds] = useState<string[]>([]);
    const rolesOn = !!apiKeyRolesEnabled;
    const roleFollowsScopes = rolesOn && !roleChosen;
    const effectiveRole = !rolesOn ? null : roleFollowsScopes ? lowestRoleFor(scopes) : role;
    const effectiveFormScope: KeyFormScope = rolesOn ? formScope : 'all';
    const listed = effectiveFormScope === 'listed';
    const problems = rolesOn ? scopeProblems(effectiveRole, effectiveFormScope, scopes) : [];
    // a scope the role or the list cannot carry is offered greyed out, with the reason; one already ticked stays
    // enabled so it can be unticked (and the problem is told above the form)
    const scopeBlockedBy = (scope: string): 'role' | 'list' | null => {
        if (!rolesOn) return null;
        if (listed && !listAllowsScope(scope)) return 'list';
        if (!roleFollowsScopes && !roleAllowsScope(effectiveRole, scope)) return 'role';
        return null;
    };
    // the keys that follow their creator's role, with the switch on: a nudge to limit them
    const [onlyFollowing, setOnlyFollowing] = useState(false);
    const [editing, setEditing] = useState<APIKey | null>(null);
    const [shownFormsOf, setShownFormsOf] = useState<string[]>([]);
    // The one and only time the full token is visible.
    const [freshToken, setFreshToken] = useState<{ name: string; token: string } | null>(null);

    const mcpUrl = `${environments.API_ENDPOINT_HOST}/mcp`;

    const toggleScope = (scope: string) => {
        setScopes((current) => (current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope]));
    };

    const handleCreate = async () => {
        const response: any = await createKey({
            workspace_id: workspace.id,
            body: {
                name: name.trim(),
                scopes,
                acknowledgeUnredactedResponses: readsResponses && acknowledged,
                // a key limited to a list submits to the forms of that list: the list is the set
                ...(submits && limitForms && !listed ? { submissionFormIds: formIds } : {}),
                ...(rolesOn && effectiveRole ? { role: effectiveRole } : {}),
                ...(rolesOn && listed ? { formScope: 'listed', formIds: listedIds } : {})
            }
        });
        if (response.data) {
            setFreshToken({ name: response.data.name, token: response.data.token });
            setName('');
            setScopes(['forms:read']);
            setAcknowledged(false);
            setLimitForms(false);
            setFormIds([]);
            setRole(null);
            setRoleChosen(false);
            setFormScope('all');
            setListedIds([]);
        } else {
            toast({ description: keyErrorText(t, response.error, 'STAFF.API_KEYS.CREATE_FAILED'), variant: 'destructive' });
        }
    };

    const handleRevoke = async (key: APIKey) => {
        if (!window.confirm(t('STAFF.API_KEYS.REVOKE_CONFIRM', { name: key.name }))) return;
        const response: any = await revokeKey({ workspace_id: workspace.id, key_id: key.id });
        if (response.data) {
            toast({ description: t('STAFF.API_KEYS.REVOKED_TOAST', { name: key.name }) });
        } else {
            toast({ description: t('STAFF.API_KEYS.REVOKE_FAILED'), variant: 'destructive' });
        }
    };

    // keys with no role of their own follow their creator's: with the switch on, a nudge to limit the live ones
    const followingCount = (keys as APIKey[]).filter((key) => !key.revoked && keyRoleOf(key) === null && !key.role).length;
    const visibleKeys = (keys as APIKey[]).filter((key) => !onlyFollowing || (!key.revoked && !key.role));

    if (!canManageKeys) {
        return (
            <div className="pb-10">
                <p className="text-black-600 text-sm">{t('STAFF.API_KEYS.ONLY_ADMINS')}</p>
            </div>
        );
    }

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 pb-10">
            <div className="flex flex-col gap-1.5">
                <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                    {t('STAFF.API_KEYS.INTRO')}
                </p>
            </div>

            <div className="flex flex-col gap-2">
                <h2 className="text-black-900 text-sm font-semibold">{t('STAFF.API_KEYS.ENDPOINT')}</h2>
                <p className="text-black-600 text-xs leading-relaxed">{t('STAFF.API_KEYS.ENDPOINT_HELP')}</p>
                <div className="border-black-400 bg-black-50 flex items-center justify-between gap-3 rounded-md border px-3.5 py-2.5">
                    <code className="text-black-800 truncate text-[13px]">{mcpUrl}</code>
                    <CopyButton value={mcpUrl} label={t('STAFF.API_KEYS.COPY_ENDPOINT')} />
                </div>
            </div>

            {freshToken && (
                <div className="flex flex-col gap-2 rounded-md border border-[#B7E0CD] bg-[#F0FAF5] p-4">
                    <p className="text-black-900 text-sm font-semibold">{t('STAFF.API_KEYS.COPY_NOW', { name: freshToken.name })}</p>
                    <p className="text-black-600 text-xs leading-relaxed">{t('STAFF.API_KEYS.ONLY_ONCE')}</p>
                    <div className="border-black-300 flex items-center justify-between gap-3 rounded-md border bg-white px-3.5 py-2.5">
                        <code className="text-black-800 truncate text-[13px]">{freshToken.token}</code>
                        <CopyButton value={freshToken.token} label={t('STAFF.API_KEYS.COPY_KEY')} />
                    </div>
                    <div>
                        <Button size="sm" variant="v2GhostButton" onClick={() => setFreshToken(null)}>
                            {t('STAFF.API_KEYS.SAVED')}
                        </Button>
                    </div>
                </div>
            )}

            <div className="flex flex-col gap-3">
                <h2 className="text-black-900 text-sm font-semibold">{t('STAFF.API_KEYS.CREATE_TITLE')}</h2>
                <input
                    value={name}
                    maxLength={60}
                    placeholder={t('STAFF.API_KEYS.NAME_PLACEHOLDER')}
                    onChange={(e) => setName(e.target.value)}
                    className="border-control text-black-900 placeholder:text-black-600 focus:border-brand-500 h-10 w-full rounded-md border bg-white px-3.5 text-sm outline-hidden transition duration-150"
                />
                <div className="flex flex-col gap-1.5">
                    {scopeChoices.map((scope) => {
                        const blocked = !scopes.includes(scope.key) ? scopeBlockedBy(scope.key) : null;
                        return (
                            <label key={scope.key} className={`flex items-start gap-2.5 ${blocked ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}>
                                <input type="checkbox" checked={scopes.includes(scope.key)} disabled={!!blocked} onChange={() => toggleScope(scope.key)} className="mt-0.5 h-4 w-4 cursor-pointer" />
                                <span className="flex flex-col">
                                    <span className="text-black-800 text-[13px] font-medium">{t(scope.label)}</span>
                                    <span className="text-black-600 text-xs">{blocked ? t(blocked === 'list' ? 'STAFF.API_KEYS.HINT_LIST_CANNOT' : 'STAFF.API_KEYS.HINT_ROLE_CANNOT') : t(scope.hint)}</span>
                                </span>
                            </label>
                        );
                    })}
                </div>
                {rolesOn && <ScopeProblems role={effectiveRole} formScope={effectiveFormScope} scopes={scopes} />}
                {rolesOn && (
                    <KeyLimitsFields
                        idPrefix="new-key"
                        scopes={scopes}
                        role={role}
                        roleFollowsScopes={roleFollowsScopes}
                        onRoleChange={(next) => {
                            setRole(next);
                            setRoleChosen(true);
                        }}
                        formScope={formScope}
                        onFormScopeChange={setFormScope}
                        formIds={listedIds}
                        onFormIdsChange={setListedIds}
                        hideScopeProblems
                    />
                )}
                {submits && listed && <p className="text-black-700 max-w-[62ch] text-xs leading-relaxed">{t('STAFF.API_KEYS.SUBMITS_TO_LIST')}</p>}
                {submits && !listed && (
                    <fieldset className="border-black-300 flex flex-col gap-2 rounded-md border p-3">
                        <legend className="text-black-900 px-1 text-[13px] font-semibold">{t('STAFF.API_KEYS.SUBMISSIONS_TITLE')}</legend>
                        <p className="text-black-700 text-xs leading-relaxed">{t('STAFF.API_KEYS.SUBMISSIONS_BODY')}</p>
                        <label className="text-black-800 flex cursor-pointer items-start gap-2 text-xs">
                            <input type="checkbox" checked={limitForms} onChange={(e) => setLimitForms(e.target.checked)} className="mt-0.5 h-4 w-4" />
                            <span>{t('STAFF.API_KEYS.LIMIT_FORMS')}</span>
                        </label>
                        {limitForms &&
                            (formChoices.length === 0 ? (
                                <p className="text-black-600 text-xs">{t('STAFF.API_KEYS.NO_PUBLISHED_FORMS')}</p>
                            ) : (
                                <ul className="flex max-h-48 flex-col gap-1 overflow-y-auto pl-6">
                                    {formChoices.map((form) => (
                                        <li key={form.formId}>
                                            <label className="text-black-800 flex cursor-pointer items-center gap-2 text-xs">
                                                <input type="checkbox" checked={formIds.includes(form.formId)} onChange={() => setFormIds((current) => (current.includes(form.formId) ? current.filter((id) => id !== form.formId) : [...current, form.formId]))} className="h-4 w-4" />
                                                <span className="truncate">{form.title?.trim() || t('STAFF.API_KEYS.UNTITLED_FORM')}</span>
                                            </label>
                                        </li>
                                    ))}
                                </ul>
                            ))}
                        {limitForms && moreForms && (
                            <div className="pl-6">
                                <Button size="sm" variant="v2GhostButton" onClick={() => setFormsPage((current) => current + 1)}>
                                    {t('STAFF.API_KEYS.MORE_FORMS')}
                                </Button>
                            </div>
                        )}
                    </fieldset>
                )}
                {readsResponses && (
                    <div className="flex flex-col gap-2 rounded-md border border-[#F0D9B5] bg-[#FDF8EF] p-3" role="alert">
                        <p className="text-black-900 text-[13px] font-semibold">{t('STAFF.API_KEYS.WARN_TITLE')}</p>
                        <p className="text-black-700 text-xs leading-relaxed">
                            {t('STAFF.API_KEYS.WARN_BODY')}
                        </p>
                        <label className="text-black-800 flex cursor-pointer items-start gap-2 text-xs">
                            <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} className="mt-0.5 h-4 w-4" />
                            <span>{t('STAFF.API_KEYS.ACKNOWLEDGE')}</span>
                        </label>
                    </div>
                )}
                <div>
                    <Button size="medium" variant="primary" isLoading={isCreating} disabled={!name.trim() || scopes.length === 0 || (readsResponses && !acknowledged) || (submits && limitForms && !listed && formIds.length === 0) || problems.length > 0 || (listed && listedIds.length === 0)} onClick={handleCreate}>
                        {t('STAFF.API_KEYS.CREATE')}
                    </Button>
                </div>
            </div>

            <div className="flex flex-col gap-3">
                <h2 className="text-black-900 text-sm font-semibold">{t('STAFF.API_KEYS.YOUR_KEYS')}</h2>
                {rolesOn && followingCount > 0 && (
                    <div className="border-black-300 bg-black-50 flex flex-wrap items-center justify-between gap-2 rounded-md border px-3.5 py-2.5">
                        <p className="text-black-800 text-xs leading-relaxed">{t('STAFF.API_KEYS.REVIEW_BANNER', { count: followingCount })}</p>
                        <Button type="button" size="sm" variant="v2Button" className="min-h-11 sm:min-h-0" aria-pressed={onlyFollowing} onClick={() => setOnlyFollowing((current) => !current)}>
                            {onlyFollowing ? t('STAFF.API_KEYS.REVIEW_SHOW_ALL') : t('STAFF.API_KEYS.REVIEW_SHOW')}
                        </Button>
                    </div>
                )}
                {isLoading ? (
                    <p className="text-black-600 text-xs">{t('STAFF.COMMON.LOADING')}</p>
                ) : keys.length === 0 ? (
                    <p className="text-black-600 border-black-400 rounded-md border border-dashed px-3 py-4 text-center text-xs">{t('STAFF.API_KEYS.NONE')}</p>
                ) : (
                    <ul className="flex flex-col gap-2">
                        {visibleKeys.map((key) => (
                            <li key={key.id} className={`border-black-300 flex items-start justify-between gap-3 rounded-md border px-3.5 py-3 ${key.revoked ? 'opacity-60' : ''}`}>
                                <div className="flex min-w-0 flex-col gap-1">
                                    <div className="flex items-center gap-2">
                                        <KeyRound className="text-black-600 h-3.5 w-3.5 shrink-0" />
                                        <span className="text-black-900 truncate text-[13px] font-medium">{key.name}</span>
                                        <code className="text-black-600 text-xs">{key.prefix}…</code>
                                        {key.revoked && <span className="rounded bg-[#FBEFEF] px-1.5 py-0.5 text-[10.5px] font-medium text-[#C43D3D]">{t('STAFF.API_KEYS.REVOKED')}</span>}
                                    </div>
                                    {(rolesOn || key.role != null || keyFormScopeOf(key) === 'listed') && (
                                        <div className="flex flex-wrap items-center gap-1.5">
                                            <span className="bg-black-100 text-black-800 rounded px-1.5 py-0.5 text-[11px] font-medium">{keyRoleOf(key) ? t('STAFF.API_KEYS.ROLE_CHIP', { role: t(roleNameKey(keyRoleOf(key) as KeyRole)) }) : key.role ? t('STAFF.API_KEYS.ROLE_CHIP_UNKNOWN', { role: key.role }) : t('STAFF.API_KEYS.ROLE_CHIP_CREATOR')}</span>
                                            {keyFormScopeOf(key) === 'listed' ? (
                                                <button
                                                    type="button"
                                                    aria-expanded={shownFormsOf.includes(key.id)}
                                                    aria-controls={`key-forms-${key.id}`}
                                                    onClick={() => setShownFormsOf((current) => (current.includes(key.id) ? current.filter((id) => id !== key.id) : [...current, key.id]))}
                                                    className="bg-black-100 text-black-800 hover:bg-black-200 flex min-h-11 items-center rounded px-1.5 py-0.5 text-[11px] font-medium sm:min-h-0"
                                                >
                                                    {t('STAFF.API_KEYS.FORMS_CHIP_COUNT', { count: key.forms?.length ?? 0 })}
                                                </button>
                                            ) : (
                                                <span className="bg-black-100 text-black-800 rounded px-1.5 py-0.5 text-[11px] font-medium">{t('STAFF.API_KEYS.FORMS_CHIP_ALL')}</span>
                                            )}
                                        </div>
                                    )}
                                    {keyFormScopeOf(key) === 'listed' && shownFormsOf.includes(key.id) && (
                                        <ul id={`key-forms-${key.id}`} className="text-black-700 flex list-disc flex-col gap-0.5 pl-5 text-xs">
                                            {(key.forms ?? []).map((form) => (
                                                <li key={form.id}>{form.title?.trim() || t('STAFF.API_KEYS.UNKNOWN_FORM')}</li>
                                            ))}
                                        </ul>
                                    )}
                                    <div className="flex flex-wrap items-center gap-1.5">
                                        {key.scopes.map((scope) => (
                                            <span key={scope} className="bg-black-100 text-black-600 rounded px-1.5 py-0.5 text-[10.5px]">
                                                {scope}
                                            </span>
                                        ))}
                                        <span className="text-black-600 text-[10.5px]">{key.lastUsedAt ? t('STAFF.API_KEYS.LAST_USED', { date: new Date(key.lastUsedAt).toLocaleString(locale) }) : t('STAFF.API_KEYS.NEVER_USED')}</span>
                                        {key.scopes.includes(SUBMISSIONS_SCOPE.key) && <span className="text-black-600 text-[10.5px]">· {key.submissionFormIds?.length ? t('STAFF.API_KEYS.SUBMITS_TO_FORMS', { count: key.submissionFormIds.length }) : t('STAFF.API_KEYS.SUBMITS_TO_ALL')}</span>}
                                        {key.responsesReadAcknowledgedAt && <span className="text-black-600 text-[10.5px]">· {t('STAFF.API_KEYS.ACKNOWLEDGED_ON', { date: new Date(key.responsesReadAcknowledgedAt).toLocaleDateString(locale) })}</span>}
                                    </div>
                                </div>
                                {!key.revoked && (
                                    <div className="flex shrink-0 flex-col items-end sm:flex-row">
                                        {rolesOn && (
                                            <button type="button" aria-label={t('STAFF.API_KEYS.EDIT_KEY', { name: key.name })} onClick={() => setEditing(key)} className="text-black-600 hover:bg-black-200 hover:text-black-900 min-h-11 min-w-11 rounded px-2 py-1 text-xs transition-colors sm:min-h-0 sm:min-w-0">
                                                {t('STAFF.API_KEYS.EDIT')}
                                            </button>
                                        )}
                                        <button type="button" aria-label={rolesOn ? t('STAFF.API_KEYS.REVOKE_KEY', { name: key.name }) : undefined} onClick={() => handleRevoke(key)} className="text-black-600 min-h-11 min-w-11 shrink-0 rounded px-2 py-1 text-xs transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D] sm:min-h-0 sm:min-w-0">
                                            {t('STAFF.API_KEYS.REVOKE')}
                                        </button>
                                    </div>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
            {rolesOn && editing && (
                <EditKeyDialog
                    keyItem={editing}
                    workspaceId={workspace.id}
                    onClose={() => setEditing(null)}
                    onReload={async () => {
                        const reloaded: any = await refetch();
                        return (reloaded?.data as APIKey[] | undefined)?.find((other) => other.id === editing.id);
                    }}
                    onSaved={(savedName) => toast({ description: t('STAFF.API_KEYS.SAVED_TOAST', { name: savedName }) })}
                />
            )}
        </div>
    );
}
