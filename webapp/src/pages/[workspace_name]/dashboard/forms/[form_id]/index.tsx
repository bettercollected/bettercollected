import React, { useEffect } from 'react';

import Router from 'next/router';

import { Feed, Settings } from '@mui/icons-material';

import FormSubmissionsTab from '@app/components/dashboard/dashboard-responses-tab-content';
import FormSettingsTab from '@app/components/dashboard/form-settings';
import { FormTabContent } from '@app/components/dashboard/form-tab-content';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { HistoryIcon } from '@app/components/icons/history';
import { HomeIcon } from '@app/components/icons/home';
import { TrashIcon } from '@app/components/icons/trash';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import ParamTab from '@app/components/ui/param-tab';
import { TabPanel } from '@app/components/ui/tab';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import Error from '@app/pages/_error';
import { initialFormState, setForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function FormPage(props: any) {
    const { form } = props;
    const breakpoint = useBreakpoint();
    if (!props && Object.keys(props).length === 0) {
        return <Error />;
    }

    const breadcrumbsItem = [
        {
            title: 'Forms',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: () => Router.push(`/${props?.workspace?.workspaceName}/dashboard`)
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title, 30) : form?.title
        }
    ];

    return (
        <FormPageLayout {...props}>
            <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />
            <FormTabContent form={form} />
        </FormPageLayout>
    );
}
export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
