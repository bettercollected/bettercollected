'use client';

import { useTranslation } from 'react-i18next';

import { useEmailActionsStatus } from '@app/components/email-actions/use-email-actions-status';
import { useRegistrationEnabled } from '@app/components/registration/use-registration-enabled';
import { useWebhooksEnabled } from '@app/components/webhooks/use-webhooks-enabled';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetEmailActionsQuery, useGetEmailDeliveriesQuery } from '@app/store/workspaces/email-actions-api';
import { useGetFormRegistrationQuery, useGetRegistrationDeliveriesQuery } from '@app/store/workspaces/registration-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useGetWebhookDeliveriesQuery, useGetWebhooksQuery } from '@app/store/workspaces/webhooks-api';
import { ATTENTION_STATUSES } from '@app/utils/registration';

import { CardKind } from './panels';
import { Chip, chipFor, failedCount, listStats, shortList } from './summary';

/** Everything a card shows and which buttons it has; the section turns it into a card and its sheets. */
export interface CardData {
    kind: CardKind;
    title: string;
    summary: string;
    chip: Chip | null;
    /** Manage (or Set up while nothing is set up). Needs workspace.manage, as the section did. */
    canManage: boolean;
    setUp: boolean;
    /** The deliveries log, where there is one to read. */
    hasDeliveries: boolean;
}

// The same arguments the deliveries components use for their counts, so the
// queries are shared (one request, not two) once a drawer opens.
const NOT_SENT = ['failed', 'cancelled'] as ('failed' | 'cancelled')[];

function useFormTarget() {
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const provider = form?.settings?.provider;
    // An imported form is not collected here: no automation applies.
    const ready = !!workspace?.id && !!form?.formId && !(provider && provider !== 'self');
    return { ready, workspaceId: workspace?.id ?? '', formId: form?.formId ?? '' };
}

/** Webhooks: owners and admins configure, editors see the deliveries, while this server has webhooks on. */
export function useWebhooksCard(): CardData | null {
    const { t } = useTranslation('builder');
    const { t: tc } = useTranslation();
    const { enabled } = useWebhooksEnabled();
    const { can } = useWorkspacePermissions();
    const { ready, workspaceId, formId } = useFormTarget();
    const canManage = enabled && ready && can(WorkspacePermission.WORKSPACE_MANAGE);
    const canSee = canManage || (enabled && ready && can(WorkspacePermission.FORM_EDIT));
    const hooks = useGetWebhooksQuery({ workspaceId, formId }, { skip: !canManage });
    const failedQuery = useGetWebhookDeliveriesQuery({ workspaceId, formId, status: NOT_SENT, limit: 1 }, { skip: !canSee });
    if (!canSee) return null;

    const failed = failedCount(failedQuery.data, failedQuery.error);
    const forbidden = (failedQuery.error as { status?: number } | undefined)?.status === 403;
    const known = canManage && !!hooks.data;
    const stats = listStats(
        hooks.data,
        (hook) => hook.enabled,
        (hook) => hook.host
    );
    const configured = stats.total > 0;
    const summary = known && configured ? [tc('STAFF.FORM_SETTINGS.CARD_ON_OF', { on: stats.on, count: stats.total }), shortList(stats.labels)].filter(Boolean).join(' · ') : tc('STAFF.FORM_SETTINGS.CARD_WEBHOOKS_DESC');
    return {
        kind: 'webhooks',
        title: t('WEBHOOKS.TITLE'),
        summary,
        chip: known ? chipFor({ configured, on: stats.on > 0, failed }) : failed ? { kind: 'not-sent', count: failed } : null,
        canManage,
        setUp: known && !configured,
        hasDeliveries: !forbidden && (!canManage || configured || (failed ?? 0) > 0)
    };
}

/** Email: the same split as webhooks, while this server has email actions on. */
export function useEmailCard(): CardData | null {
    const { t } = useTranslation('builder');
    const { t: tc } = useTranslation();
    const { enabled, configured: mailServer } = useEmailActionsStatus();
    const { can } = useWorkspacePermissions();
    const { ready, workspaceId, formId } = useFormTarget();
    const canManage = enabled && ready && can(WorkspacePermission.WORKSPACE_MANAGE);
    const canSee = canManage || (enabled && ready && can(WorkspacePermission.FORM_EDIT));
    const actions = useGetEmailActionsQuery({ workspaceId, formId }, { skip: !canManage });
    const failedQuery = useGetEmailDeliveriesQuery({ workspaceId, formId, status: NOT_SENT, limit: 1 }, { skip: !canSee });
    if (!canSee) return null;

    const failed = failedCount(failedQuery.data, failedQuery.error);
    const forbidden = (failedQuery.error as { status?: number } | undefined)?.status === 403;
    const known = canManage && !!actions.data;
    const stats = listStats(
        actions.data,
        (action) => action.enabled,
        () => undefined
    );
    const configured = stats.total > 0;
    // "This server has no mail server" is the summary of a card that has actions but cannot send them.
    const noMailServer = canManage && !mailServer;
    const summary = noMailServer ? t('EMAIL_ACTIONS.NOT_CONFIGURED') : known && configured ? tc('STAFF.FORM_SETTINGS.CARD_ON_OF', { on: stats.on, count: stats.total }) : tc('STAFF.FORM_SETTINGS.CARD_EMAIL_DESC');
    return {
        kind: 'email',
        title: t('EMAIL_ACTIONS.TITLE'),
        summary,
        chip: known ? chipFor({ configured, on: stats.on > 0, failed, unavailable: noMailServer }) : failed ? { kind: 'not-sent', count: failed } : null,
        canManage,
        setUp: known && !configured,
        hasDeliveries: !forbidden && (!canManage || configured || (failed ?? 0) > 0)
    };
}

/** Case system: owners and admins, while this server sends to case systems. */
export function useCaseSystemCard(): CardData | null {
    const { t: tc } = useTranslation();
    const { enabled } = useRegistrationEnabled();
    const { can } = useWorkspacePermissions();
    const { ready, workspaceId, formId } = useFormTarget();
    const canManage = enabled && ready && can(WorkspacePermission.WORKSPACE_MANAGE);
    const canRead = canManage && can(WorkspacePermission.RESPONSE_READ);
    const registration = useGetFormRegistrationQuery({ workspaceId, formId }, { skip: !canManage });
    const failedQuery = useGetRegistrationDeliveriesQuery({ workspaceId, formId, status: [...ATTENTION_STATUSES], limit: 1 }, { skip: !canRead });
    const deliveredQuery = useGetRegistrationDeliveriesQuery({ workspaceId, formId, status: ['delivered'], limit: 1 }, { skip: !canRead });
    if (!canManage) return null;

    const failed = failedCount(failedQuery.data, failedQuery.error);
    const delivered = (deliveredQuery.data?.total ?? 0) > 0;
    const data = registration.data;
    const serviceName = data?.serviceName;
    const configured = !!data && (data.enabled || !!serviceName);
    const summary = serviceName ? tc('STAFF.FORM_SETTINGS.CARD_SENDS_TO', { service: serviceName }) : tc('STAFF.FORM_SETTINGS.CARD_CASE_SYSTEM_DESC');
    return {
        kind: 'case-system',
        title: tc('STAFF.FORM_SETTINGS.CARD_CASE_SYSTEM'),
        summary,
        chip: data ? chipFor({ configured, on: data.enabled, failed }) : failed ? { kind: 'not-sent', count: failed } : null,
        canManage,
        setUp: !!data && !configured,
        // The same rule as the log itself: a form that never sent, and is off, has nothing to show.
        hasDeliveries: canRead && ((data?.enabled ?? false) || (failed ?? 0) > 0 || delivered)
    };
}
