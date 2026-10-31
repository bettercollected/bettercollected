'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import SecretOnce from '@app/components/webhooks/secret-once';
import { useWebhooksEnabled } from '@app/components/webhooks/use-webhooks-enabled';
import WebhookDeliveries from '@app/components/webhooks/webhook-deliveries';
import WebhookEditor from '@app/components/webhooks/webhook-editor';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import {
    Webhook,
    WebhookVariable,
    WebhookWithSecret,
    useGetWebhookDetailQuery,
    useDeleteWebhookMutation,
    useGetWebhookVariablesQuery,
    useGetWebhooksQuery,
    useRotateWebhookSecretMutation,
    useSendWebhookTestMutation,
    useUpdateWebhookMutation
} from '@app/store/workspaces/webhooks-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { errorCodeOf, errorKey } from '@app/utils/webhooks';

/**
 * The Settings tab's "Webhooks": owners and admins (workspace.manage) send the
 * answers of chosen questions to an https address of their own, while this
 * server has webhooks on, for forms built here. Editors who cannot manage
 * webhooks still see the deliveries. Renders nothing otherwise.
 */
export default function FormWebhooksSection() {
    const { enabled } = useWebhooksEnabled();
    const { can } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const provider = form?.settings?.provider;
    if (!enabled || !workspace?.id || !form?.formId || (provider && provider !== 'self')) return null;
    if (can(WorkspacePermission.WORKSPACE_MANAGE)) return <WebhooksSettings workspaceId={workspace.id} formId={form.formId} />;
    if (can(WorkspacePermission.FORM_EDIT)) return <WebhookDeliveries workspaceId={workspace.id} formId={form.formId} />;
    return null;
}

type Editing = { kind: 'add' } | { kind: 'edit'; id: string } | null;
type Pending = { kind: 'delete' | 'rotate'; id: string } | null;

export function WebhooksSettings({ workspaceId, formId }: { workspaceId: string; formId: string }) {
    const { t } = useTranslation('builder');
    const hooks = useGetWebhooksQuery({ workspaceId, formId });
    const variables = useGetWebhookVariablesQuery({ workspaceId, formId });
    const [update] = useUpdateWebhookMutation();
    const [remove] = useDeleteWebhookMutation();
    const [rotate] = useRotateWebhookSecretMutation();
    const [sendTest] = useSendWebhookTestMutation();
    const [editing, setEditing] = useState<Editing>(null);
    const [pending, setPending] = useState<Pending>(null);
    const [secret, setSecret] = useState<{ value: string; host: string; rotated: boolean } | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [message, setMessage] = useState<{ text: string; failed: boolean } | null>(null);

    const list = hooks.data ?? [];
    const loading = hooks.isLoading || variables.isLoading;
    const failed = hooks.isError || variables.isError;
    const say = (text: string, failedCall = false) => setMessage({ text, failed: failedCall });

    const run = async (id: string, call: () => Promise<any>, done?: (data: any) => void) => {
        setBusy(id);
        setMessage(null);
        const response = await call();
        setBusy(null);
        if (response.error) say(t(errorKey(errorCodeOf(response.error))), true);
        else done?.(response.data);
    };

    const toggle = (hook: Webhook, enabled: boolean) =>
        run(
            hook.id,
            () => update({ workspaceId, formId, webhookId: hook.id, body: { enabled } }),
            () => say(t(enabled ? 'WEBHOOKS.LIST.SWITCHED_ON' : 'WEBHOOKS.LIST.SWITCHED_OFF', { host: hook.host }))
        );

    const test = (hook: Webhook) =>
        run(
            hook.id,
            () => sendTest({ workspaceId, formId, webhookId: hook.id }),
            () => say(t('WEBHOOKS.LIST.TEST_QUEUED', { host: hook.host }))
        );

    const rotateSecret = (hook: Webhook) => {
        setPending(null);
        return run(
            hook.id,
            () => rotate({ workspaceId, formId, webhookId: hook.id }),
            (data: WebhookWithSecret) => setSecret({ value: data.secret, host: hook.host, rotated: true })
        );
    };

    const deleteHook = (hook: Webhook) => {
        setPending(null);
        return run(
            hook.id,
            () => remove({ workspaceId, formId, webhookId: hook.id }),
            () => say(t('WEBHOOKS.LIST.DELETED', { host: hook.host }))
        );
    };

    const editingHook = editing?.kind === 'edit' ? list.find((h) => h.id === editing.id) : undefined;

    return (
        <>
            <section className="flex flex-col gap-4" aria-labelledby="webhooks-title" data-testid="webhooks-section">
                <h2 id="webhooks-title" className="text-xs font-semibold tracking-wide text-black-600 uppercase">
                    {t('WEBHOOKS.TITLE')}
                </h2>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('WEBHOOKS.INTRO')}</p>
                <p className="max-w-[62ch] rounded-md border border-black-300 bg-black-100 px-3 py-2 text-xs leading-relaxed text-black-700">{t('WEBHOOKS.NOTICE')}</p>

                {loading && <p className="text-sm text-black-600">{t('WEBHOOKS.LOADING')}</p>}
                {failed && (
                    <p role="alert" className="text-sm text-[#A83434]">
                        {t('WEBHOOKS.LOAD_ERROR')}
                    </p>
                )}

                <p role="status" className={message?.failed ? 'text-sm font-medium text-[#A83434]' : 'text-sm text-black-800'}>
                    {message?.text ?? ''}
                </p>

                {secret && <SecretOnce secret={secret.value} host={secret.host} rotated={secret.rotated} onDone={() => setSecret(null)} />}

                {!loading && !failed && (
                    <>
                        {list.length === 0 && editing?.kind !== 'add' && <p className="text-sm text-black-700">{t('WEBHOOKS.LIST.NONE')}</p>}
                        <ul className="flex flex-col gap-3" aria-label={t('WEBHOOKS.LIST.LABEL')}>
                            {list.map((hook) => {
                                const confirming = pending?.id === hook.id ? pending.kind : null;
                                return (
                                    <li key={hook.id} className="flex flex-col gap-3 rounded-lg border border-black-300 bg-white p-4" data-testid={`webhook-${hook.id}`}>
                                        {editing?.kind === 'edit' && editing.id === hook.id && editingHook ? (
                                            <EditWebhook
                                                workspaceId={workspaceId}
                                                formId={formId}
                                                hook={editingHook}
                                                variables={variables.data ?? []}
                                                onSaved={() => {
                                                    setEditing(null);
                                                    say(t('WEBHOOKS.LIST.SAVED', { host: hook.host }));
                                                }}
                                                onCancel={() => setEditing(null)}
                                            />
                                        ) : (
                                            <>
                                                <div className="flex flex-wrap items-center justify-between gap-3">
                                                    <div className="flex min-w-0 flex-col">
                                                        <span className="text-sm font-semibold break-all text-black-900">{hook.host}</span>
                                                        <span className="text-xs text-black-600">{t('WEBHOOKS.LIST.QUESTIONS', { count: hook.fields.length })}</span>
                                                        {hook.condition && hook.condition.conditions.length > 0 && <span className="text-xs text-black-600">{t('ACTION_CONDITION.BADGE')}</span>}
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <Switch
                                                            id={`webhook-on-${hook.id}`}
                                                            checked={hook.enabled}
                                                            disabled={busy === hook.id}
                                                            aria-label={t('WEBHOOKS.LIST.ENABLED_FOR', { host: hook.host })}
                                                            onCheckedChange={(checked) => toggle(hook, checked)}
                                                        />
                                                        <span className="text-sm text-black-800" aria-hidden="true">
                                                            {t(hook.enabled ? 'WEBHOOKS.LIST.ON' : 'WEBHOOKS.LIST.OFF')}
                                                        </span>
                                                    </div>
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    <Button type="button" variant="v2Button" size="sm" disabled={busy === hook.id} onClick={() => setEditing({ kind: 'edit', id: hook.id })} aria-label={t('WEBHOOKS.LIST.EDIT_NAMED', { host: hook.host })}>
                                                        {t('WEBHOOKS.LIST.EDIT')}
                                                    </Button>
                                                    <Button type="button" variant="v2Button" size="sm" isLoading={busy === hook.id} disabled={busy !== null} onClick={() => test(hook)} aria-label={t('WEBHOOKS.LIST.TEST_NAMED', { host: hook.host })}>
                                                        {t('WEBHOOKS.LIST.TEST')}
                                                    </Button>
                                                    <Button type="button" variant="v2Button" size="sm" disabled={busy !== null} onClick={() => setPending({ kind: 'rotate', id: hook.id })} aria-label={t('WEBHOOKS.LIST.ROTATE_NAMED', { host: hook.host })}>
                                                        {t('WEBHOOKS.LIST.ROTATE')}
                                                    </Button>
                                                    <Button type="button" variant="dangerGhost" size="sm" disabled={busy !== null} onClick={() => setPending({ kind: 'delete', id: hook.id })} aria-label={t('WEBHOOKS.LIST.DELETE_NAMED', { host: hook.host })}>
                                                        {t('WEBHOOKS.LIST.DELETE')}
                                                    </Button>
                                                </div>
                                                {confirming && (
                                                    <div role="alertdialog" aria-labelledby={`webhook-confirm-${hook.id}`} className="flex flex-col gap-2 rounded-md border border-[#E5B9B9] bg-[#FBEFEF] p-3">
                                                        <p id={`webhook-confirm-${hook.id}`} className="text-sm text-black-900">
                                                            {t(confirming === 'delete' ? 'WEBHOOKS.LIST.CONFIRM_DELETE' : 'WEBHOOKS.LIST.CONFIRM_ROTATE', { host: hook.host })}
                                                        </p>
                                                        <div className="flex flex-wrap gap-2">
                                                            <Button type="button" size="sm" variant={confirming === 'delete' ? 'danger' : 'primary'} onClick={() => (confirming === 'delete' ? deleteHook(hook) : rotateSecret(hook))}>
                                                                {t(confirming === 'delete' ? 'WEBHOOKS.LIST.DELETE' : 'WEBHOOKS.LIST.ROTATE')}
                                                            </Button>
                                                            <Button type="button" size="sm" variant="v2Button" onClick={() => setPending(null)}>
                                                                {t('WEBHOOKS.EDITOR.CANCEL')}
                                                            </Button>
                                                        </div>
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </li>
                                );
                            })}
                        </ul>

                        {editing?.kind === 'add' ? (
                            <WebhookEditor
                                workspaceId={workspaceId}
                                formId={formId}
                                variables={variables.data ?? []}
                                onCreated={(created) => {
                                    setEditing(null);
                                    setSecret({ value: created.secret, host: created.host, rotated: false });
                                }}
                                onSaved={() => setEditing(null)}
                                onCancel={() => setEditing(null)}
                            />
                        ) : (
                            <div>
                                <Button type="button" variant="v2Button" size="sm" onClick={() => setEditing({ kind: 'add' })} data-testid="webhook-add">
                                    {t('WEBHOOKS.LIST.ADD')}
                                </Button>
                            </div>
                        )}
                    </>
                )}
            </section>
            <WebhookDeliveries workspaceId={workspaceId} formId={formId} />
        </>
    );
}

/**
 * The editor of an existing webhook. The list never carries an address (it can
 * hold a token): this reads the owner-facing view, which opens it, and only
 * while the webhook is being edited.
 */
function EditWebhook({ workspaceId, formId, hook, variables, onSaved, onCancel }: { workspaceId: string; formId: string; hook: Webhook; variables: WebhookVariable[]; onSaved: () => void; onCancel: () => void }) {
    const { t } = useTranslation('builder');
    const detail = useGetWebhookDetailQuery({ workspaceId, formId, webhookId: hook.id });
    if (detail.isLoading) return <p className="text-sm text-black-600">{t('WEBHOOKS.LOADING')}</p>;
    return (
        <>
            {detail.isError && (
                <p role="alert" className="text-sm font-medium text-[#A83434]">
                    {t(errorKey(errorCodeOf(detail.error)))}
                </p>
            )}
            {/* a webhook whose address cannot be read is edited with the address left empty: entering it again repairs it */}
            <WebhookEditor workspaceId={workspaceId} formId={formId} variables={variables} webhook={detail.data ?? { ...hook, url: '' }} onCreated={() => undefined} onSaved={onSaved} onCancel={onCancel} />
        </>
    );
}
