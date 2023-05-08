import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';

import ResponsesTable from '@app/components/datatable/responses';
import FormPageLayout from '@app/components/sidebar/form-page-layout';

export default function DeletionRequests(props: any) {
    const { formId } = props;

    return (
        <FormPageLayout {...props}>
            <div className="heading4">Deletion Requests</div>
            <Divider className="my-4" />
            <ResponsesTable formId={formId} workspaceId={props.workspace.id} requestForDeletion={true} />
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
