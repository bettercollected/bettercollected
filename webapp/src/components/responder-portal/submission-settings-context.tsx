'use client';

import { useModal } from '@app/components/modal-views/context';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { Button } from '@app/shadcn/components/ui/button';
import { utcToLocalDateIn } from '@app/utils/date-utils';
import { deletionStatusLabel } from '@Components/workspace-client/workspace-form-response-deletion-card';
import { Shield } from 'lucide-react';
import { useSubmissionContext } from './submission-context';

export default function SubmissionSettingsContent() {
    const { t, language } = useRespondentLanguage();
    const { openModal } = useModal();
    const { data, handleRequestForDeletion } = useSubmissionContext();
    const form = data ?? {};

    const deletionStatus: string | undefined = form?.response?.deletionStatus || undefined;

    const handleRequestForDeletionModal = () => {
        openModal('REQUEST_FOR_DELETION_VIEW', { handleRequestForDeletion: handleRequestForDeletion });
    };

    return (
        // The deletion right, stated in plain words and kept calm — this is a
        // trust surface, not a danger zone (DESIGN.md §4/§5). In the
        // respondent's language, like the rest of the page.
        <div className="flex max-w-[640px] flex-col gap-4" lang={language}>
            <div className="flex items-start gap-2 rounded-lg bg-[#F4F7FD] px-3 py-2.5">
                <Shield className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" strokeWidth={1.8} aria-hidden="true" />
                <span className="text-black-700 text-sm leading-relaxed">{t('SUBMISSION.OWNERSHIP')}</span>
            </div>
            {!deletionStatus ? (
                <div className="flex flex-col gap-2">
                    {/* No Tooltip wrapper: the shared Tooltip renders its own
                        <button> trigger, nesting buttons (hydration error). */}
                    <Button className="w-fit" variant="danger" onClick={handleRequestForDeletionModal}>
                        {t('SUBMISSION.REQUEST')}
                    </Button>
                    <span className="text-black-600 text-xs">{t('SUBMISSION.REQUEST_HINT')}</span>
                </div>
            ) : deletionStatus === 'pending' ? (
                <div className="flex flex-col gap-2">
                    <span className="w-fit rounded bg-brand-accent-100 px-2 py-1 text-sm font-medium text-brand-olive">{t('SUBMISSION.PENDING')}</span>
                    <span className="text-black-600 text-sm">{t('SUBMISSION.PENDING_TEXT')}</span>
                </div>
            ) : (
                // Closed: a declined request says it was NOT deleted, and why.
                <span className="w-fit rounded bg-black-100 px-2 py-1 text-sm font-medium text-black-700">{deletionStatusLabel(deletionStatus, form?.response?.declineReason, utcToLocalDateIn(form?.response?.updatedAt, language), t)}</span>
            )}
        </div>
    );
}
