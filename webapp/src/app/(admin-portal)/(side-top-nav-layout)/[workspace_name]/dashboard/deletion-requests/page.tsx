"use client";

import { useEffect, useState } from 'react';

import SearchInput from '@Components/common/search-input';

import ResponsesTable from '@Components/datatable/responses-table';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceAllSubmissionsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetAllSubmissionsQuery } from '@app/store/workspaces/types';

export default function DeletionRequests() {
    const workspace = useAppSelector(selectWorkspace);
    const [page, setPage] = useState(1);

    const workspaceId = workspace?.id || '';

    const workspaceStats = useGetWorkspaceStatsQuery(workspaceId, {
        pollingInterval: 30000,
        skip: !workspaceId
    });

    const [query, setQuery] = useState<IGetAllSubmissionsQuery>({
        workspaceId: workspaceId,
        requestedForDeletionOly: true,
        page: page,
        size: globalConstants.pageSize
    });

    // Update query when workspaceId or page changes
    useEffect(() => {
        if (workspaceId) {
            setTimeout(() => {
                setQuery((prev) => ({
                    ...prev,
                    workspaceId: workspaceId,
                    page: page
                }));
            }, 0);
        }
    }, [workspaceId, page]);

    const handleSearch = (event: any) => {
        if (event.target.value) {
            setQuery({ ...query, dataOwnerIdentifier: event.target.value, page: 1 });
            setPage(1);
        } else {
            const { dataOwnerIdentifier, ...removedQuery } = query;
            setQuery({ ...removedQuery, page: 1 });
            setPage(1);
        }
    };

    const { data, isLoading } = useGetWorkspaceAllSubmissionsQuery(query, {
        skip: !workspaceId
    });

    if (!workspaceId) return null;

    return (
        <div className="flex flex-col">
            {isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {data && (
                <>
                    {/* No h1 here — the sticky top bar already titles the page.
                        "5/5 deletion remaining" read like a quota; say what the
                        number is — how many requests still need handling. */}
                    <p className="body1 text-black-900 mb-10 mt-2">
                        {(workspaceStats?.data?.deletionRequests.pending || 0) === 0
                            ? (workspaceStats?.data?.deletionRequests.total || 0) === 0
                                ? 'No deletion requests yet.'
                                : 'All deletion requests handled.'
                            : `${workspaceStats?.data?.deletionRequests.pending} of ${workspaceStats?.data?.deletionRequests.total} requests pending — deleting the response completes a request.`}
                    </p>
                    <div className="w-full md:w-[282px] mb-8">
                        <SearchInput placeholder="Search by responder email" handleSearch={handleSearch} />
                    </div>
                    <ResponsesTable requestForDeletion={true} page={page} setPage={setPage} submissions={data} />
                </>
            )}
        </div>
    );
}
