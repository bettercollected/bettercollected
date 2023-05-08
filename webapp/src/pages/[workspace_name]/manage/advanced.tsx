import React, { useEffect, useState } from 'react';

import BetterInput from '@app/components/Common/input';
import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import UpdateCustomDomain from '@app/components/settings/advanced/update-custom-domain';
import UpdateHandle from '@app/components/settings/advanced/update-handle';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';

export default function AdvancedSettings({ workspace }: any) {
    return (
        <ManageWorkspaceLayout>
            <div className="h4">Advanced Settings</div>
            <UpdateHandle />
            <UpdateCustomDomain />
        </ManageWorkspaceLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
