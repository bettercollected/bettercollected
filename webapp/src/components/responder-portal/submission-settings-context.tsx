'use client';

import { useModal } from '@app/components/modal-views/context';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { Button } from '@app/shadcn/components/ui/button';
import { Shield } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useSubmissionContext } from './submission-context';

export default function SubmissionSettingsContent() {
    const { t } = useTranslation();
    const { openModal } = useModal();
    const { data, handleRequestForDeletion } = useSubmissionContext();
    const form = data ?? {};

    const deletionStatus = !!form?.response?.deletionStatus;

    const handleRequestForDeletionModal = () => {
        openModal('REQUEST_FOR_DELETION_VIEW', { handleRequestForDeletion: handleRequestForDeletion });
    };

    return (
        // The deletion right, stated in plain words and kept calm — this is a
        // trust surface, not a danger zone (Design-Language §4/§5).
        <div className="flex max-w-[640px] flex-col gap-4">
            <div className="flex items-start gap-2 rounded-lg bg-[#F4F7FD] px-3 py-2.5">
                <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[#2456CC]" strokeWidth={1.8} aria-hidden="true" />
                <span className="text-black-700 text-sm leading-relaxed">
                    This response belongs to you. You can ask for it to be deleted at any time — the request and its status stay visible here and under Deletion requests.
                </span>
            </div>
            {!form?.response?.deletionStatus ? (
                <div className="flex flex-col gap-2">
                    {/* No Tooltip wrapper: the shared Tooltip renders its own
                        <button> trigger, nesting buttons (hydration error). */}
                    <Button className={`w-fit`} variant="danger" title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)} onClick={handleRequestForDeletionModal}>
                        Request deletion
                    </Button>
                    <span className="text-black-600 text-xs">The workspace reviews deletion requests — you&apos;ll see the status change here once it&apos;s handled.</span>
                </div>
            ) : (
                <div className="flex flex-col gap-2">
                    <span className="w-fit rounded bg-[#FBF3E4] px-2 py-1 text-sm font-medium text-[#B26B00]">Deletion requested · Pending</span>
                    <span className="text-black-600 text-sm">The workspace has been asked to delete this response. Its status will update here and under Deletion requests.</span>
                </div>
            )}
        </div>
    );
}
