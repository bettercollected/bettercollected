import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import { toast } from 'react-toastify';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import ResponsesTable from '@app/components/datatable/responses';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import BackButton from '@app/components/settings/back';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { formsConstant } from '@app/constants/locales/forms';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';

export default function Responses(props: any) {
    const { formId } = props;

    const router = useRouter();
    let submissionId: string = (router?.query?.sub_id as string) ?? '';
    const [trigger, { isLoading, isError, error }] = useLazyGetWorkspaceSubmissionQuery();
    const { t } = useTranslation();
    const [form, setForm] = useState<any>([]);
    const requestForDeletion = false;

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
            <div className="heading4">{t(formsConstant.responses)}</div>
            {!submissionId && (
                <>
                    <Divider className="my-4" />
                    <FormResponsesTable props={{ ...props, requestForDeletion }} />
                </>
            )}
            {!!form && !!submissionId && (
                <>
                    <BackButton />
                    <FormRenderer form={form.form} response={form.response} />
                </>
            )}
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
