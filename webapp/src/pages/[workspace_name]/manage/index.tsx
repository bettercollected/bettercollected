import React from 'react';

import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import WorkspaceImage from '@app/components/settings/basic-information/worksapce-image';
import WorkspaceBanner from '@app/components/settings/basic-information/workspace-banner';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';

export default function ManageWorkspace({ workspace }: any) {
    return (
        <ManageWorkspaceLayout>
            <WorkspaceBanner />
            <WorkspaceImage />
            <WorkspaceInfo workspace={workspace} />
        </ManageWorkspaceLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
