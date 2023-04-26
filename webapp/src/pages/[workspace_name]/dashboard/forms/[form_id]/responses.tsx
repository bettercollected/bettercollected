import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import { Divider } from '@mui/material';
import TablePagination from '@mui/material/TablePagination';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import FormSubmissionsTab from '@app/components/dashboard/dashboard-responses-tab-content';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import ResponsesTable from '@app/components/datatable/responses';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import globalConstants from '@app/constants/global';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { useGetWorkspaceSubmissionsQuery, useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

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

    const breakpoint = useBreakpoint();

    const handleRemoveSubmissionId = () => {
        const updatedQuery = { ...router.query };
        delete updatedQuery.sub_id;
        router.push({
            pathname: router.pathname,
            query: updatedQuery
        });
    };

    const breadcrumbsItem = [
        {
            title: 'Responses',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: handleRemoveSubmissionId
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(submissionId, 10) : submissionId
        }
    ];

    return (
        <FormPageLayout {...props}>
            {!!submissionId && <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />}
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
