import React from 'react';

import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';

export default function ManageWorkspace() {
    return <ManageWorkspaceLayout></ManageWorkspaceLayout>;
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
