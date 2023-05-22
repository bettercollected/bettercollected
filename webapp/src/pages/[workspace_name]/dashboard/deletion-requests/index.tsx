import { useState, useTransition } from 'react';

import { useTranslation } from 'next-i18next';

import { Divider } from '@mui/material';

import ResponsesTable from '@app/components/datatable/responses';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import globalConstants from '@app/constants/global';
import { formsConstant } from '@app/constants/locales/forms';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceAllSubmissionsQuery } from '@app/store/workspaces/api';

export default function DeletionRequests({ workspace }: { workspace: WorkspaceDto }) {
    const { t } = useTranslation();
    const [page, setPage] = useState(1);

    const submissions = useGetWorkspaceAllSubmissionsQuery({
        workspaceId: workspace.id,
        requestedForDeletionOly: true,
        page: page,
        size: globalConstants.pageSize
    });
    console.log(submissions);
    return (
        <DashboardLayout>
            <div className="heading4">{t(formsConstant.deletionRequests)}</div>
            <ResponsesTable workspaceId={workspace.id} requestForDeletion={true} page={page} setPage={setPage} submissions={submissions} />
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
