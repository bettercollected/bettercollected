'use client';

import { Lock } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { StandardFormDto } from '@app/models/dtos/form';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormAccessQuery } from '@app/store/workspaces/form-access-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { cn } from '@app/shadcn/util/lib';

/**
 * "Restricted": only selected people and teams can open this form in the dashboard. A word with a lock, never
 * colour or the icon alone. The `title` says what it means for anyone who hovers it.
 */
export function RestrictedChip({ className }: { className?: string }) {
    const { t } = useTranslation();
    return (
        <span data-testid="restricted-chip" title={t('STAFF.FORM_ACCESS.CHIP_TITLE')} className={cn('inline-flex shrink-0 items-center gap-1 rounded-full bg-black-200 px-2 py-0.5 text-xs font-semibold text-black-700', className)}>
            <Lock className="h-3 w-3" aria-hidden="true" />
            {t('STAFF.FORM_ACCESS.CHIP_RESTRICTED')}
        </span>
    );
}

/**
 * The chip in a form's bar: from the form's access answer (shared with the Access settings, one request), asked
 * only while the server has form-level access on and only once the form is known.
 */
export function FormBarRestrictedChip({ form, className }: { form?: StandardFormDto; className?: string }) {
    const { formAccessEnabled } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const skip = !formAccessEnabled || !workspace?.id || !form?.formId;
    const { data } = useGetFormAccessQuery({ workspaceId: workspace?.id as string, formId: form?.formId as string }, { skip });
    if (skip || !data?.enabled || !data.restricted) return null;
    return <RestrictedChip className={className} />;
}

/**
 * The chip on a dashboard card or row: from the `access` block of the form in the list, so it asks for nothing.
 * Shown only while the server has form-level access on.
 */
export function CardRestrictedChip({ form, className }: { form?: StandardFormDto; className?: string }) {
    const { formAccessEnabled } = useWorkspacePermissions();
    if (!formAccessEnabled || !form?.access?.restricted) return null;
    return <RestrictedChip className={className} />;
}
