import React from 'react';

import { FormTabContent } from '@app/components/dashboard/form-tab-content';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import Back from '@app/components/icons/back';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import Error from '@app/pages/_error';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function FormPage(props: any) {
    const { form }: { form: StandardFormDto } = props;
    if (!props && Object.keys(props).length === 0) {
        return <Error />;
    }

    return (
        <FormPageLayout {...props}>
            <FormTabContent form={form} />
        </FormPageLayout>
    );
}
export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
