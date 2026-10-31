'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import EmailActionEditor from '@app/components/email-actions/email-action-editor';
import EmailDeliveries from '@app/components/email-actions/email-deliveries';
import { useEmailActionsStatus } from '@app/components/email-actions/use-email-actions-status';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { EmailAction, useDeleteEmailActionMutation, useGetEmailActionsQuery, useGetEmailVariablesQuery, useSendEmailTestMutation, useUpdateEmailActionMutation } from '@app/store/workspaces/email-actions-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { errorKey } from '@app/utils/email-actions';
import { errorCodeOf } from '@app/utils/webhooks';

/**
 * The Settings tab's "Email": owners and admins (workspace.manage) mail the
 * form's team and, if they choose, a copy to the respondent, while this server
 * has email actions on, for forms built here. Editors who cannot manage
 * actions still see the sent mails. Renders nothing otherwise.
 */
export default function FormEmailActionsSection() {
    const { enabled, configured } = useEmailActionsStatus();
    const { can } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const provider = form?.settings?.provider;
    if (!enabled || !workspace?.id || !form?.formId || (provider && provider !== 'self')) return null;
    if (can(WorkspacePermission.WORKSPACE_MANAGE)) return <EmailActionsSettings workspaceId={workspace.id} formId={form.formId} configured={configured} />;
    if (can(WorkspacePermission.FORM_EDIT)) return <EmailDeliveries workspaceId={workspace.id} formId={form.formId} />;
    return null;
}

type Editing = { kind: 'add' } | { kind: 'edit'; id: string } | null;

export function EmailActionsSettings({ workspaceId, formId, configured }: { workspaceId: string; formId: string; configured: boolean }) {
    const { t } = useTranslation('builder');
    const actions = useGetEmailActionsQuery({ workspaceId, formId });
    const variables = useGetEmailVariablesQuery({ workspaceId, formId });
    const [update] = useUpdateEmailActionMutation();
    const [remove] = useDeleteEmailActionMutation();
    const [sendTest] = useSendEmailTestMutation();
    const [editing, setEditing] = useState<Editing>(null);
    const [confirming, setConfirming] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [message, setMessage] = useState<{ text: string; failed: boolean } | null>(null);

    const list = actions.data ?? [];
    const loading = actions.isLoading || variables.isLoading;
    const failed = actions.isError || variables.isError;
    const say = (text: string, failedCall = false) => setMessage({ text, failed: failedCall });

    const run = async (id: string, call: () => Promise<any>, done?: (data: any) => void) => {
        setBusy(id);
        setMessage(null);
        const response = await call();
        setBusy(null);
        if (response.error) say(t(errorKey(errorCodeOf(response.error))), true);
        else done?.(response.data);
    };

    const toggle = (action: EmailAction, enabled: boolean) =>
        run(
            action.id,
            () => update({ workspaceId, formId, actionId: action.id, body: { enabled } }),
            () => say(t(enabled ? 'EMAIL_ACTIONS.LIST.SWITCHED_ON' : 'EMAIL_ACTIONS.LIST.SWITCHED_OFF', { name: action.name }))
        );

    const test = (action: EmailAction, channel: 'team' | 'respondent') =>
        run(
            action.id,
            () => sendTest({ workspaceId, formId, actionId: action.id, channel }),
            (data) => say(t(data?.status === 'delivered' ? 'EMAIL_ACTIONS.LIST.TEST_SENT' : 'EMAIL_ACTIONS.LIST.TEST_FAILED', { name: action.name }), data?.status !== 'delivered')
        );

    const deleteAction = (action: EmailAction) => {
        setConfirming(null);
        return run(
            action.id,
            () => remove({ workspaceId, formId, actionId: action.id }),
            () => say(t('EMAIL_ACTIONS.LIST.DELETED', { name: action.name }))
        );
    };

    const editingAction = editing?.kind === 'edit' ? list.find((a) => a.id === editing.id) : undefined;

    return (
        <>
            <section className="flex flex-col gap-4" aria-labelledby="email-actions-title" data-testid="email-actions-section">
                <h2 id="email-actions-title" className="text-xs font-semibold tracking-wide text-black-600 uppercase">
                    {t('EMAIL_ACTIONS.TITLE')}
                </h2>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('EMAIL_ACTIONS.INTRO')}</p>
                <p className="max-w-[62ch] rounded-md border border-black-300 bg-black-100 px-3 py-2 text-xs leading-relaxed text-black-700">{t('EMAIL_ACTIONS.NOTICE')}</p>
                {!configured && (
                    <p role="alert" className="max-w-[62ch] text-sm font-medium text-[#A83434]">
                        {t('EMAIL_ACTIONS.NOT_CONFIGURED')}
                    </p>
                )}
                {loading && <p className="text-sm text-black-600">{t('EMAIL_ACTIONS.LOADING')}</p>}
                {failed && (
                    <p role="alert" className="text-sm text-[#A83434]">
                        {t('EMAIL_ACTIONS.LOAD_ERROR')}
                    </p>
                )}
                <p role="status" className={message?.failed ? 'text-sm font-medium text-[#A83434]' : 'text-sm text-black-800'}>
                    {message?.text ?? ''}
                </p>

                {!loading && !failed && (
                    <>
                        {list.length === 0 && editing?.kind !== 'add' && <p className="text-sm text-black-700">{t('EMAIL_ACTIONS.LIST.NONE')}</p>}
                        <ul className="flex flex-col gap-3" aria-label={t('EMAIL_ACTIONS.LIST.LABEL')}>
                            {list.map((action) => (
                                <li key={action.id} className="flex flex-col gap-3 rounded-lg border border-black-300 bg-white p-4" data-testid={`email-action-${action.id}`}>
                                    {editing?.kind === 'edit' && editing.id === action.id && editingAction ? (
                                        <EmailActionEditor
                                            workspaceId={workspaceId}
                                            formId={formId}
                                            variables={variables.data ?? []}
                                            action={editingAction}
                                            onSaved={() => {
                                                setEditing(null);
                                                say(t('EMAIL_ACTIONS.LIST.SAVED', { name: action.name }));
                                            }}
                                            onCancel={() => setEditing(null)}
                                        />
                                    ) : (
                                        <>
                                            <div className="flex flex-wrap items-center justify-between gap-3">
                                                <div className="flex min-w-0 flex-col">
                                                    <span className="text-sm font-semibold break-words text-black-900">{action.name}</span>
                                                    <span className="text-xs text-black-600">
                                                        {[action.teamRecipients.length > 0 ? t('EMAIL_ACTIONS.LIST.TEAM', { count: action.teamRecipients.length }) : null, action.respondentField ? t('EMAIL_ACTIONS.LIST.COPY') : null, action.condition && action.condition.conditions.length > 0 ? t('ACTION_CONDITION.BADGE') : null]
                                                            .filter(Boolean)
                                                            .join(' · ')}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Switch id={`email-on-${action.id}`} checked={action.enabled} disabled={busy === action.id} aria-label={t('EMAIL_ACTIONS.LIST.ENABLED_FOR', { name: action.name })} onCheckedChange={(checked) => toggle(action, checked)} />
                                                    <span className="text-sm text-black-800" aria-hidden="true">
                                                        {t(action.enabled ? 'EMAIL_ACTIONS.LIST.ON' : 'EMAIL_ACTIONS.LIST.OFF')}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="flex flex-wrap gap-2">
                                                <Button type="button" variant="v2Button" size="sm" disabled={busy === action.id} onClick={() => setEditing({ kind: 'edit', id: action.id })} aria-label={t('EMAIL_ACTIONS.LIST.EDIT_NAMED', { name: action.name })}>
                                                    {t('EMAIL_ACTIONS.LIST.EDIT')}
                                                </Button>
                                                <Button type="button" variant="v2Button" size="sm" isLoading={busy === action.id} disabled={busy !== null || !configured} onClick={() => test(action, 'team')} aria-label={t('EMAIL_ACTIONS.LIST.TEST_NAMED', { name: action.name })}>
                                                    {t('EMAIL_ACTIONS.LIST.TEST')}
                                                </Button>
                                                {action.respondentField && (
                                                    <Button type="button" variant="v2Button" size="sm" disabled={busy !== null || !configured} onClick={() => test(action, 'respondent')} aria-label={t('EMAIL_ACTIONS.LIST.TEST_COPY_NAMED', { name: action.name })}>
                                                        {t('EMAIL_ACTIONS.LIST.TEST_COPY')}
                                                    </Button>
                                                )}
                                                <Button type="button" variant="dangerGhost" size="sm" disabled={busy !== null} onClick={() => setConfirming(action.id)} aria-label={t('EMAIL_ACTIONS.LIST.DELETE_NAMED', { name: action.name })}>
                                                    {t('EMAIL_ACTIONS.LIST.DELETE')}
                                                </Button>
                                            </div>
                                            {confirming === action.id && (
                                                <div role="alertdialog" aria-labelledby={`email-confirm-${action.id}`} className="flex flex-col gap-2 rounded-md border border-[#E5B9B9] bg-[#FBEFEF] p-3">
                                                    <p id={`email-confirm-${action.id}`} className="text-sm text-black-900">
                                                        {t('EMAIL_ACTIONS.LIST.CONFIRM_DELETE', { name: action.name })}
                                                    </p>
                                                    <div className="flex flex-wrap gap-2">
                                                        <Button type="button" size="sm" variant="danger" onClick={() => deleteAction(action)}>
                                                            {t('EMAIL_ACTIONS.LIST.DELETE')}
                                                        </Button>
                                                        <Button type="button" size="sm" variant="v2Button" onClick={() => setConfirming(null)}>
                                                            {t('EMAIL_ACTIONS.EDITOR.CANCEL')}
                                                        </Button>
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </li>
                            ))}
                        </ul>
                        {editing?.kind === 'add' ? (
                            <EmailActionEditor workspaceId={workspaceId} formId={formId} variables={variables.data ?? []} onSaved={() => setEditing(null)} onCancel={() => setEditing(null)} />
                        ) : (
                            <div>
                                <Button type="button" variant="v2Button" size="sm" onClick={() => setEditing({ kind: 'add' })} data-testid="email-add">
                                    {t('EMAIL_ACTIONS.LIST.ADD')}
                                </Button>
                            </div>
                        )}
                    </>
                )}
            </section>
            <EmailDeliveries workspaceId={workspaceId} formId={formId} />
        </>
    );
}
