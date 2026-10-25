'use client';

import { useId } from 'react';

import { useTranslation } from 'react-i18next';

import { sheetsReconnect } from '@app/constants/locales/sheets-reconnect';
import { IntegrationType } from '@app/models/enums/integration-type';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useGetActionReconsentStatusQuery } from '@app/store/api-actions-api';

interface ReconsentTarget {
    workspaceId?: string;
    formId?: string;
    /** The form's action (by its id and name); only Google Sheets is asked. */
    action?: { id?: string; name?: string };
}

/**
 * Whether the form's Google Sheets action must be reconnected: its grant
 * predates `drive.file`, so the backend holds its runs back. Asked whenever
 * the action is shown; false for any other action and while unknown.
 */
export function useSheetsNeedsReconnect({ workspaceId, formId, action }: ReconsentTarget): boolean {
    const isSheets = action?.name === IntegrationType.GoogleSheet;
    const { data } = useGetActionReconsentStatusQuery({ workspaceId: workspaceId ?? '', formId: formId ?? '', actionId: action?.id ?? '' }, { skip: !isSheets || !workspaceId || !formId || !action?.id });
    return isSheets && data?.needs_reconsent === true;
}

/** Short marker next to the action's name in the form's actions list. */
export function SheetsReconnectBadge({ className }: { className?: string }) {
    const { t } = useTranslation();
    return <span className={cn('inline-flex items-center rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900', className)}>{t(sheetsReconnect.badge)}</span>;
}

interface SheetsReconnectNoticeProps {
    onReconnect: () => void;
    className?: string;
}

/** What happened and what to do, with the button that starts the Google Sheets connect flow again. */
export default function SheetsReconnectNotice({ onReconnect, className }: SheetsReconnectNoticeProps) {
    const { t } = useTranslation();
    const titleId = useId();
    return (
        <section aria-labelledby={titleId} className={cn('flex w-full flex-col items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm', className)}>
            <div role="status" className="flex flex-col gap-1">
                <p id={titleId} className="font-semibold text-black-900">
                    {t(sheetsReconnect.title)}
                </p>
                <p className="text-black-800">{t(sheetsReconnect.description)}</p>
                <p className="text-black-800">{t(sheetsReconnect.newSheet)}</p>
            </div>
            <Button variant="primary" onClick={onReconnect} data-umami-event="Reconnect Google Sheets">
                {t(sheetsReconnect.button)}
            </Button>
        </section>
    );
}
