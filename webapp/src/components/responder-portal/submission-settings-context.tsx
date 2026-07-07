'use client';

import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { Button } from '@app/shadcn/components/ui/button';
import Tooltip from '@app/shadcn/components/ui/tooltip';
import Divider from '@Components/common/divider';
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
        <div className="flex flex-col gap-[72px] px-5">
            <div className="flex flex-col gap-2">
                <span className="h3-new">Settings</span>
                <span className="p2-new text-black-700"> Review your data usage permissions</span>
            </div>
            {form?.settings?.provider !== 'self' && (
                <div className="flex max-w-[800px] flex-col gap-4">
                    <Divider />
                    <div className="h4-new">You can request for deletion of your data in this form.</div>
                    <Divider />
                </div>
            )}
            {!form?.response?.deletionStatus ? (
                <div>
                    {/* No Tooltip wrapper: the shared Tooltip renders its own
                        <button> trigger, nesting buttons (hydration error). */}
                    <Button className={`w-fit`} variant="danger" title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)} onClick={handleRequestForDeletionModal}>
                        {t(buttonConstant.requestForDeletion)}
                    </Button>
                </div>
            ) : (
                <div className="flex flex-col gap-2">
                    <span className="h4-new !text-red-500 ">You have requested for deletion of your response.</span>
                    <span>Status: Pending</span>
                </div>
            )}
        </div>
    );
}
