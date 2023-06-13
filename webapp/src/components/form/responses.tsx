import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import { toast } from 'react-toastify';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import BackButton from '@app/components/settings/back';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
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
            {!submissionId && (
                <>
                    <p className="body1">
                        {t(formConstant.responses)} ({form.responses})
                    </p>

                    <FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion }} />
                </>
            )}
            {!!submissionForm && !!submissionId && (
                <>
                    <BackButton />
                    <FormRenderer form={submissionForm.form} response={submissionForm.response} />
                </>
            )}
        </>
    );
}
