import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { ChevronLeft } from '@mui/icons-material';
import { Button } from '@mui/material';
import { toast } from 'react-toastify';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { useModal } from '@app/components/modal-views/context';
import { formPage } from '@app/constants/locales/form-page';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';
import { utcToLocalDateTIme } from '@app/utils/dateUtils';

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
                <div className="flex flex-col px-2 md:px-10 lg:px-28">
                    <div className="flex items-center justify-between ">
                        <div className="flex flex-col">
                            <span
                                className="flex gap-2 cursor-pointer"
                                onClick={() => {
                                    const { sub_id, ...otherQuery } = router.query;

                                    router.push({
                                        pathname: router.pathname,
                                        query: otherQuery
                                    });
                                }}
                            >
                                <ChevronLeft width={24} height={24} />
                                {t(formPage.responsesBackToResponses)}:
                            </span>
                        </div>

                        {form?.settings?.provider === 'self' && (
                            <Button
                                style={{ textTransform: 'none' }}
                                className="bg-red-100 px-4 !leading-none py-3 body6 rounded hover:bg-red-200 hover:drop-shadow-sm  !text-red-500"
                                size="medium"
                                onClick={() => {
                                    openModal('DELETE_RESPONSE', {
                                        workspace: workspace,
                                        formId: form.formId,
                                        responseId: submissionId,
                                        navigateToForm: true
                                    });
                                }}
                            >
                                {t(formPage.responsesDeletedResponse)}:
                            </Button>
                        )}
                    </div>
                    <div className="gap-2 flex flex-col mt-5">
                        <div className="text-sm text-black-700">
                            {t(formPage.responsesSubmittedBy)}: <b>{submissionForm?.response?.dataOwnerIdentifier || t(formPage.responsesAnonymous)}</b>
                        </div>
                        <div className="text-sm text-black-700">
                            {t(formPage.responsesSubmittedAt)}: <b>{utcToLocalDateTIme(submissionForm?.response?.createdAt) || t(formPage.responsesAnonymous)}</b>
                        </div>
                    </div>
                    <FormRenderer form={submissionForm.form} response={submissionForm.response} isDisabled />
                </div>
            )}
        </>
    );
}
