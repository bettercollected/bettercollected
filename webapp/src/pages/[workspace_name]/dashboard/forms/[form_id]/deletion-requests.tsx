import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { formsConstant } from '@app/constants/locales/forms';

export default function DeletionRequests(props: any) {
    const { t } = useTranslation();
    const requestForDeletion = true;

    return (
        <FormPageLayout {...props}>
            <div className="heading4">{t(formsConstant.deletionRequests)}</div>
            <Divider className="my-4" />
            <FormResponsesTable props={{ ...props, requestForDeletion }} />
        </FormPageLayout>
    );
}

export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
