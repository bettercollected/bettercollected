import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import { Divider } from '@mui/material';
import { toast } from 'react-toastify';

import ResponsesTable from '@app/components/datatable/responses';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';

export default function Responses(props: any) {
    const { formId } = props;

    const router = useRouter();
    let submissionId: string = (router?.query?.sub_id as string) ?? '';
    const [trigger, { isLoading, isError, error }] = useLazyGetWorkspaceSubmissionQuery();

    const [form, setForm] = useState<any>([]);

    useEffect(() => {
        if (!!submissionId) {
            const submissionQuery: IGetWorkspaceSubmissionQuery = {
                workspace_id: props.workspaceId,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d) => {
                    setForm(d.data);
                })
                .catch((e) => {
                    toast.error('Error fetching submission data.', { toastId: 'errorToast' });
                });
        }
    }, [submissionId]);

    return (
        <FormPageLayout {...props}>
            {!submissionId && (
                <>
                    <div className="heading4">Responses</div>

                    <Divider className="my-4" />
                    <ResponsesTable formId={formId} workspaceId={props.workspace.id} requestForDeletion={false} />
                </>
            )}
            {!!form && !!submissionId && <FormRenderer form={form.form} response={form.response} />}
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
