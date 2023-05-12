import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';

import ResponsesTable from '@app/components/datatable/responses';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { formsConstant } from '@app/constants/locales';

export default function DeletionRequests(props: any) {
    const { formId } = props;
    const { t } = useTranslation();

    return (
        <FormPageLayout {...props}>
            <div className="heading4">{t(formsConstant.deletionRequests)}</div>
            <Divider className="my-4" />
            <ResponsesTable formId={formId} workspaceId={props.workspace.id} requestForDeletion={true} />
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
