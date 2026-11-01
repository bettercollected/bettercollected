'use client';

import { useState } from 'react';

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

interface APIKey {
    id: string;
    name: string;
    prefix: string;
    scopes: string[];
    revoked: boolean;
    lastUsedAt?: string | null;
    responsesReadAcknowledgedAt?: string | null;
    // the forms a submissions:write key is limited to (none: every form)
    submissionFormIds?: string[] | null;
}

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
    const { can, submissionsApiEnabled } = useWorkspacePermissions();
    const canManageKeys = can(WorkspacePermission.SECURITY_MANAGE);
    const { toast } = useToast();

    const { data: keys = [], isLoading } = useGetAPIKeysQuery(workspace?.id, { skip: !workspace?.id || !canManageKeys });
    const [createKey, { isLoading: isCreating }] = useCreateAPIKeyMutation();
    const [revokeKey] = useRevokeAPIKeyMutation();

    const [name, setName] = useState('');
    const [scopes, setScopes] = useState<string[]>(['forms:read']);
    // responses:read hands full, unredacted answers to the AI client (#715)
    const [acknowledged, setAcknowledged] = useState(false);
    const readsResponses = scopes.includes('responses:read');
    // submissions:write may be limited to some of the workspace's published forms (none picked: every form)
    const submits = scopes.includes(SUBMISSIONS_SCOPE.key);
    const [limitForms, setLimitForms] = useState(false);
    const [formIds, setFormIds] = useState<string[]>([]);
    const { data: publishedForms } = useGetWorkspaceFormsQuery({ workspace_id: workspace?.id, published: true, page: 1, size: 100 }, { skip: !workspace?.id || !submits || !submissionsApiEnabled });
    const formChoices: Array<{ formId: string; title?: string }> = (publishedForms as any)?.items ?? [];
    const scopeChoices = submissionsApiEnabled ? [...SCOPES, SUBMISSIONS_SCOPE] : SCOPES;
    // The one and only time the full token is visible.
    const [freshToken, setFreshToken] = useState<{ name: string; token: string } | null>(null);

    const mcpUrl = `${environments.API_ENDPOINT_HOST}/mcp`;

    const toggleScope = (scope: string) => {
        setScopes((current) => (current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope]));
    };

    const handleCreate = async () => {
        const response: any = await createKey({
            workspace_id: workspace.id,
            body: { name: name.trim(), scopes, acknowledgeUnredactedResponses: readsResponses && acknowledged, ...(submits && limitForms ? { submissionFormIds: formIds } : {}) }
        });
        if (response.data) {
            setFreshToken({ name: response.data.name, token: response.data.token });
            setName('');
            setScopes(['forms:read']);
            setAcknowledged(false);
            setLimitForms(false);
            setFormIds([]);
        } else {
            toast({ description: response.error?.data || t('STAFF.API_KEYS.CREATE_FAILED'), variant: 'destructive' });
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
                    {scopeChoices.map((scope) => (
                        <label key={scope.key} className="flex cursor-pointer items-start gap-2.5">
                            <input type="checkbox" checked={scopes.includes(scope.key)} onChange={() => toggleScope(scope.key)} className="mt-0.5 h-4 w-4 cursor-pointer" />
                            <span className="flex flex-col">
                                <span className="text-black-800 text-[13px] font-medium">{t(scope.label)}</span>
                                <span className="text-black-600 text-xs">{t(scope.hint)}</span>
                            </span>
                        </label>
                    ))}
                </div>
                {submits && (
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
                    <Button size="medium" variant="primary" isLoading={isCreating} disabled={!name.trim() || scopes.length === 0 || (readsResponses && !acknowledged) || (submits && limitForms && formIds.length === 0)} onClick={handleCreate}>
                        {t('STAFF.API_KEYS.CREATE')}
                    </Button>
                </div>
            </div>

            <div className="flex flex-col gap-3">
                <h2 className="text-black-900 text-sm font-semibold">{t('STAFF.API_KEYS.YOUR_KEYS')}</h2>
                {isLoading ? (
                    <p className="text-black-600 text-xs">{t('STAFF.COMMON.LOADING')}</p>
                ) : keys.length === 0 ? (
                    <p className="text-black-600 border-black-400 rounded-md border border-dashed px-3 py-4 text-center text-xs">{t('STAFF.API_KEYS.NONE')}</p>
                ) : (
                    <ul className="flex flex-col gap-2">
                        {(keys as APIKey[]).map((key) => (
                            <li key={key.id} className={`border-black-300 flex items-start justify-between gap-3 rounded-md border px-3.5 py-3 ${key.revoked ? 'opacity-60' : ''}`}>
                                <div className="flex min-w-0 flex-col gap-1">
                                    <div className="flex items-center gap-2">
                                        <KeyRound className="text-black-600 h-3.5 w-3.5 shrink-0" />
                                        <span className="text-black-900 truncate text-[13px] font-medium">{key.name}</span>
                                        <code className="text-black-600 text-xs">{key.prefix}…</code>
                                        {key.revoked && <span className="rounded bg-[#FBEFEF] px-1.5 py-0.5 text-[10.5px] font-medium text-[#C43D3D]">{t('STAFF.API_KEYS.REVOKED')}</span>}
                                    </div>
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
                                    <button type="button" onClick={() => handleRevoke(key)} className="text-black-600 shrink-0 rounded px-2 py-1 text-xs transition-colors hover:bg-[#FBEFEF] hover:text-[#C43D3D]">
                                        {t('STAFF.API_KEYS.REVOKE')}
                                    </button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
