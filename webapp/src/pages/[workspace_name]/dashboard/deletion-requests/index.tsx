import { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import SearchInput from '@Components/Common/Search/SearchInput';

import ResponsesTable from '@app/Components/datatable/responses';
import DashboardLayout from '@app/Components/sidebar/dashboard-layout';
import Loader from '@app/Components/ui/loader';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceAllSubmissionsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
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
    const { data, isLoading } = useGetWorkspaceAllSubmissionsQuery(query);
    const { workspaceName } = useAppSelector(selectWorkspace);

    return (
        <DashboardLayout boxClassName="px-5 pt-10 lg:px-10">
            <NextSeo title={t(formConstant.deletionRequests) + ' | ' + workspaceName} noindex={true} nofollow={true} />
            {isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {data && (
                <>
                    <div className="heading4">{t(formConstant.deletionRequests)}</div>
                    <p className="body1 text-black-900 my-10">
                        {workspaceStats?.data?.deletionRequests.pending || 0}/{workspaceStats?.data?.deletionRequests.total || 0} {t(localesCommon.deletionRemaining)}
                    </p>
                    <div className="w-full md:w-[282px] mb-8">
                        <SearchInput handleSearch={handleSearch} />
                    </div>
                    <ResponsesTable requestForDeletion={true} page={page} setPage={setPage} submissions={data} />
                </>
            )}
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';