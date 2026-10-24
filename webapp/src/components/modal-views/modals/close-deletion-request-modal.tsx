import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { deletionRequestLocale } from '@app/constants/locales/deletion-request';
import { DECLINE_REASONS, DeclineReason, DeletionRequestOutcome, closeDeletionRequestError } from '@app/models/enums/deletion-request';
import { useCloseDeletionRequestMutation } from '@app/store/workspaces/api';

interface CloseDeletionRequestModalProps {
    workspace: { id: string };
    formId: string;
    responseId: string;
    outcome: DeletionRequestOutcome;
}

/**
 * Staff close a pending deletion request by hand (privacy.manage): mark it
 * deleted (the copy stored here is deleted; an imported response stays at
 * its source) or decline it for one of the fixed reasons, which the
 * responder sees. Never free text: the reason is a code.
 */
export default function CloseDeletionRequestModal({ workspace, formId, responseId, outcome }: CloseDeletionRequestModalProps) {
    const { t } = useTranslation();
    const { toast } = useToast();
    const { closeModal } = useModal();
    const [closeRequest, { isLoading }] = useCloseDeletionRequestMutation();
    const [reason, setReason] = useState<DeclineReason | null>(null);
    const [reasonMissing, setReasonMissing] = useState(false);
    const declining = outcome === 'declined';

    const handleClose = async () => {
        if (declining && !reason) {
            setReasonMissing(true);
            return;
        }
        const result: any = await closeRequest({ workspaceId: workspace.id, formId, responseId, outcome, ...(declining && reason ? { reason } : {}) });
        if (result?.data) {
            toast({ description: t(declining ? deletionRequestLocale.declined : deletionRequestLocale.markedDeleted) });
            closeModal();
            return;
        }
        const error = closeDeletionRequestError(result?.error);
        toast({ description: t(deletionRequestLocale[error]), variant: 'destructive' });
        if (error === 'alreadyClosed') closeModal();
    };

    return (
        <GenericHalfModal
            headerTitle={t(declining ? deletionRequestLocale.decline : deletionRequestLocale.markDeleted)}
            title={t(declining ? deletionRequestLocale.declineTitle : deletionRequestLocale.markDeletedTitle)}
            subTitle={t(declining ? deletionRequestLocale.declineDescription : deletionRequestLocale.markDeletedDescription)}
            type={declining ? 'confirmation' : 'danger'}
            positiveText={t(declining ? deletionRequestLocale.decline : deletionRequestLocale.markDeleted)}
            loading={isLoading}
            positiveAction={handleClose}
        >
            {declining && (
                <fieldset className="mt-5" aria-describedby={reasonMissing ? 'decline-reason-missing' : undefined}>
                    <legend className="text-black-800 mb-2 text-sm font-medium">{t(deletionRequestLocale.reasonLabel)}</legend>
                    <div className="flex flex-col gap-2">
                        {DECLINE_REASONS.map((code) => (
                            <label key={code} className="text-black-800 flex cursor-pointer items-start gap-2 text-sm">
                                <input
                                    type="radio"
                                    name="decline-reason"
                                    value={code}
                                    checked={reason === code}
                                    onChange={() => {
                                        setReason(code);
                                        setReasonMissing(false);
                                    }}
                                    className="mt-0.5 accent-brand-500"
                                />
                                <span>{t(deletionRequestLocale.reason(code))}</span>
                            </label>
                        ))}
                    </div>
                    {reasonMissing && (
                        <p id="decline-reason-missing" role="alert" className="mt-2 text-sm text-[#C43D3D]">
                            {t(deletionRequestLocale.reasonRequired)}
                        </p>
                    )}
                </fieldset>
            )}
        </GenericHalfModal>
    );
}
