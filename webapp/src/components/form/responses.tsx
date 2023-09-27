import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import DeleteIcon from '@Components/Common/Icons/Delete';
import { toast } from 'react-toastify';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { useModal } from '@app/components/modal-views/context';
import BackButton from '@app/components/settings/back';
import { formConstant } from '@app/constants/locales/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';

export default function FormResponses() {
    const router = useRouter();
    let submissionId: string = (router?.query?.sub_id as string) ?? '';
    const [trigger, { isLoading, isError, error }] = useLazyGetWorkspaceSubmissionQuery();
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const [submissionForm, setSubmissionForm] = useState<any>([]);
    const requestForDeletion = false;
    const { openModal } = useModal();

    useEffect(() => {
        if (!!submissionId) {
            const submissionQuery: IGetWorkspaceSubmissionQuery = {
                workspace_id: workspace.id,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d) => {
                    setSubmissionForm(d.data);
                })
                .catch((e) => {
                    toast.error('Error fetching submission data.', { toastId: 'errorToast' });
                });
        }
    }, [submissionId]);

    return (
        <>
            {!submissionId && <FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion, isSubmission: true }} />}
            {!!submissionForm && !!submissionId && (
                <>
                    <div className="flex items-center justify-between">
                        <BackButton />
                        {form?.settings?.provider === 'self' && (
                            <div className="cursor-pointer hover:bg-gray-200 p-2 h-min rounded">
                                <DeleteIcon
                                    onClick={() => {
                                        openModal('DELETE_RESPONSE', {
                                            workspace: workspace,
                                            formId: form.formId,
                                            responseId: submissionId,
                                            navigateToForm: true
                                        });
                                    }}
                                />
                            </div>
                        )}
                    </div>
                    <FormRenderer form={submissionForm.form} response={submissionForm.response} isDisabled />
                </>
            )}
        </>
    );
}
