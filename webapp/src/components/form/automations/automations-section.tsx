'use client';

import React, { useState } from 'react';

import Image from 'next/image';

import { Briefcase, Mail, Webhook } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { EmailActionsSettings } from '@app/components/email-actions/email-actions-section';
import EmailDeliveries from '@app/components/email-actions/email-deliveries';
import { useEmailActionsStatus } from '@app/components/email-actions/use-email-actions-status';
import { useSheetsNeedsReconnect } from '@app/components/form-integrations/sheets-reconnect-notice';
import FormIntegrations from '@app/components/form/integrations';
import { useModal } from '@app/components/modal-views/context';
import { Deliveries } from '@app/components/registration/deliveries-panel';
import { FormRegistrationSettings } from '@app/components/registration/form-registration-settings';
import WebhookDeliveries from '@app/components/webhooks/webhook-deliveries';
import { WebhooksSettings } from '@app/components/webhooks/webhooks-section';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { Action } from '@app/models/dtos/actions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@app/shadcn/components/ui/sheet';
import { useGetAllIntegrationsQuery } from '@app/store/api-actions-api';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import AutomationCard from './automation-card';
import { Panel, panelName } from './panels';
import { Chip, chipFor } from './summary';
import { CardData, useCaseSystemCard, useEmailCard, useWebhooksCard } from './use-cards';
import { usePanel } from './use-panel';

const ICONS = {
    email: <Mail size={20} />,
    webhooks: <Webhook size={20} />,
    'case-system': <Briefcase size={20} />
};

/** One card of a built-in kind, from its data. */
function KindCard({ data, onOpen }: { data: CardData; onOpen: (panel: Panel) => void }) {
    return (
        <AutomationCard
            id={data.kind}
            title={data.title}
            summary={data.summary}
            icon={ICONS[data.kind]}
            chip={data.chip}
            manage={data.canManage ? { setUp: data.setUp, onClick: () => onOpen({ kind: data.kind, view: 'manage' }), opener: panelName({ kind: data.kind, view: 'manage' }) } : undefined}
            deliveries={data.hasDeliveries ? { onClick: () => onOpen({ kind: data.kind, view: 'deliveries' }), opener: panelName({ kind: data.kind, view: 'deliveries' }) } : undefined}
        />
    );
}

/** One integration action (today Google Sheets): on/off from the form, "Reconnect needed" from its status. */
function IntegrationCard({ integration, onOpen }: { integration: Action; onOpen: (panel: Panel) => void }) {
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const state = form?.actions?.on_submit?.find((action: any) => action.id === integration.id);
    const reconnect = useSheetsNeedsReconnect({ workspaceId: workspace?.id, formId: form?.formId, action: integration });
    const chip: Chip = chipFor({ configured: !!state, on: !!state?.enabled, reconnect });
    const title = integration.title || t('STAFF.INTEGRATIONS.UNTITLED');
    const opener = panelName({ kind: 'action', actionId: integration.id, view: 'manage' });
    return (
        <AutomationCard
            id={`action-${integration.id}`}
            title={title}
            summary={integration.description || t('STAFF.FORM_SETTINGS.CARD_NOT_SET_UP')}
            icon={<Image src={integration.url || '/integration/default.svg'} alt="" width={24} height={24} />}
            chip={chip}
            manage={{
                setUp: !state,
                opener,
                // Setting one up is the dialog it always was; managing one opens its sheet.
                onClick: () => (state ? onOpen({ kind: 'action', actionId: integration.id, view: 'manage' }) : openModal('ADD_ACTION_TO_FORM', { action: integration, form }))
            }}
        />
    );
}

/** The side sheet of a card: its title, a line about it, and the existing component as its body. */
function CardSheet({ panel, cards, integrations }: { panel: Panel; cards: CardData[]; integrations: Action[] }) {
    const { t } = useTranslation();
    const { t: tb } = useTranslation('builder');
    const { can } = useWorkspacePermissions();
    const { configured } = useEmailActionsStatus();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const descriptionId = React.useId();
    if (!workspace?.id || !form?.formId) return null;
    const workspaceId = workspace.id;
    const formId = form.formId;

    let title = '';
    let description: string | undefined;
    let body: React.ReactNode = null;

    if (panel.kind === 'action') {
        const integration = integrations.find((item) => item.id === panel.actionId);
        if (!integration) return null;
        title = integration.title || t('STAFF.INTEGRATIONS.UNTITLED');
        description = integration.description;
        body = <FormIntegrations onlyActionId={integration.id} headless />;
    } else {
        const card = cards.find((item) => item.kind === panel.kind);
        if (!card) return null;
        title = panel.view === 'deliveries' ? t('STAFF.FORM_SETTINGS.CARD_DELIVERIES_TITLE', { name: card.title }) : card.title;
        if (panel.view === 'manage' && !card.canManage) return null;
        if (panel.view === 'deliveries' && !card.hasDeliveries) return null;
        if (panel.kind === 'webhooks') {
            description = panel.view === 'manage' ? tb('WEBHOOKS.INTRO') : tb('WEBHOOKS.DELIVERIES.INTRO');
            body = panel.view === 'manage' ? <WebhooksSettings workspaceId={workspaceId} formId={formId} headless /> : <WebhookDeliveries workspaceId={workspaceId} formId={formId} headless />;
        } else if (panel.kind === 'email') {
            description = panel.view === 'manage' ? tb('EMAIL_ACTIONS.INTRO') : tb('EMAIL_ACTIONS.DELIVERIES.INTRO');
            body = panel.view === 'manage' ? <EmailActionsSettings workspaceId={workspaceId} formId={formId} configured={configured} headless /> : <EmailDeliveries workspaceId={workspaceId} formId={formId} headless />;
        } else {
            description = panel.view === 'manage' ? tb('REGISTRATION.FORM.INTRO') : undefined;
            body =
                panel.view === 'manage' ? (
                    <FormRegistrationSettings workspaceId={workspaceId} workspaceName={workspace.workspaceName} formId={formId} headless />
                ) : (
                    <Deliveries workspaceId={workspaceId} formId={formId} canRetry={can(WorkspacePermission.FORM_EDIT)} headless />
                );
        }
    }

    return (
        <SheetContent
            side="right"
            data-testid="automation-sheet"
            aria-describedby={description ? descriptionId : undefined}
            // Full width on a phone; the existing editors need room on a desktop. Slides honour reduced motion (sheet.tsx).
            className="flex w-full flex-col gap-4 overflow-y-auto sm:max-w-[560px]"
            onCloseAutoFocus={(event) => {
                // Back to the button that opened the sheet (also when a link opened it and the button never had focus).
                event.preventDefault();
                document.querySelector<HTMLElement>(`[data-panel-opener="${panelName(panel)}"]`)?.focus();
            }}
        >
            <SheetHeader className="pr-10 text-left">
                <SheetTitle className="text-xl">{title}</SheetTitle>
                {description && (
                    <SheetDescription id={descriptionId} className="max-w-[62ch] leading-relaxed">
                        {description}
                    </SheetDescription>
                )}
            </SheetHeader>
            {body}
        </SheetContent>
    );
}

/**
 * The Settings tab's "Automations": one compact card per thing that happens to
 * each response (email, webhooks, a case system, each integration action).
 * A card says what it does in one line and whether it is on; Manage opens the
 * existing settings in a side sheet, Deliveries opens the existing log. Who
 * sees which card is exactly what each of those sections already decided.
 */
export default function AutomationsSection() {
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
    const { panel, open, close } = usePanel();
    const webhooks = useWebhooksCard();
    const email = useEmailCard();
    const caseSystem = useCaseSystemCard();

    const isSelf = form?.settings?.provider === 'self';
    // Google Sheets and other integration actions: forms built here, published (the Settings tab itself needs form.edit).
    const showIntegrations = isSelf && form?.builderVersion === 'v2' && !!form?.isPublished;
    const { data } = useGetAllIntegrationsQuery({}, { skip: !showIntegrations });
    const integrations = showIntegrations && Array.isArray(data) ? data : [];

    const cards = [email, webhooks, caseSystem].filter((card): card is CardData => !!card);
    // The sheet stays mounted while it slides out, with what it showed.
    const [lastPanel, setLastPanel] = useState<Panel | null>(null);
    const openName = panel ? panelName(panel) : null;
    if (panel && openName !== (lastPanel ? panelName(lastPanel) : null)) setLastPanel(panel);
    const shown = panel ?? lastPanel;

    if (cards.length === 0 && integrations.length === 0) return null;

    return (
        <section id="automations" aria-labelledby="automations-title" className="flex scroll-mt-6 flex-col gap-2">
            <h2 id="automations-title" className="text-xl font-semibold text-black-900">
                {t('STAFF.FORM_SETTINGS.AUTOMATIONS')}
            </h2>
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.FORM_SETTINGS.AUTOMATIONS_INTRO')}</p>
            <ul className="mt-2 flex flex-col gap-3" aria-label={t('STAFF.FORM_SETTINGS.AUTOMATIONS')}>
                {cards.map((card) => (
                    <KindCard key={card.kind} data={card} onOpen={open} />
                ))}
                {integrations.map((integration) => (
                    <IntegrationCard key={integration.id} integration={integration} onOpen={open} />
                ))}
            </ul>
            <Sheet open={!!panel} onOpenChange={(next) => !next && close()}>
                {shown && <CardSheet panel={shown} cards={cards} integrations={integrations} />}
            </Sheet>
        </section>
    );
}
