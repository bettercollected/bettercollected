import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';

import ResponsesTable from '@app/components/datatable/responses';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceAllSubmissionsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { IGetAllSubmissionsQuery } from '@app/store/workspaces/types';

export default function DeletionRequests({ workspace }: { workspace: WorkspaceDto }) {
    const { t } = useTranslation();
    const [page, setPage] = useState(1);
    const workspaceStats = useGetWorkspaceStatsQuery(workspace.id, { pollingInterval: 30000 });
    const [query, setQuery] = useState<IGetAllSubmissionsQuery>({
        workspaceId: workspace.id,
        requestedForDeletionOly: true,
        page: page,
        size: globalConstants.pageSize
    });
    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({ ...query, dataOwnerIdentifier: event.target.value });
        else {
            const { dataOwnerIdentifier, ...removedQuery } = query;
            setQuery(removedQuery);
        }
    };
    const submissions = useGetWorkspaceAllSubmissionsQuery(query);
    return (
        <DashboardLayout>
            {submissions?.isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {!submissions?.isLoading && (
                <>
                    <div className="heading4">{t(formConstant.deletionRequests)}</div>
                    <p className="body1 text-black-900 my-10">
                        {workspaceStats?.data?.deletion_requests.pending || 0}/{workspaceStats?.data?.deletion_requests.total || 0} {t(localesCommon.deletionRemaining)}
                    </p>
                    <div className="w-full md:w-[282px] mb-8">
                        <SearchInput handleSearch={handleSearch} />
                    </div>
                    <ResponsesTable workspaceId={workspace.id} requestForDeletion={true} page={page} setPage={setPage} submissions={submissions} />
                </>
            )}
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
