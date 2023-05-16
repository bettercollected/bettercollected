import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import UpdateCustomDomain from '@app/components/settings/advanced/update-custom-domain';
import UpdateHandle from '@app/components/settings/advanced/update-handle';
import { advanceSetting } from '@app/constants/locales/advance-setting';

export default function AdvancedSettings({ workspace }: any) {
    const { t } = useTranslation();
    return (
        <ManageWorkspaceLayout>
            <div className="h4">{t(advanceSetting.default)}</div>
            <UpdateHandle />
            <UpdateCustomDomain />
        </ManageWorkspaceLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
