import React from 'react';

import FormSubmissionsTab from '@app/components/dashboard/dashboard-responses-tab-content';
import FormPageLayout from '@app/components/sidebar/form-page-layout';

export default function DeletionRequests(props: any) {
    const { formId } = props;

    return (
        <FormPageLayout {...props}>
            <FormSubmissionsTab workspace={props.workspace} workspaceName={props?.workspace?.workspaceName} workspaceId={props?.workspace?.id ?? ''} formId={formId} requestedForDeletion />
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
