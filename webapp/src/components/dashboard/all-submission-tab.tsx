import React, { useEffect, useState } from 'react';

import TablePagination from '@mui/material/TablePagination';

import SubmissionsGrid from '@app/components/cards/submission-container';
import EmptyFormsView from '@app/components/dashboard/empty-form';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import globalConstants from '@app/constants/global';
import DynamicContainer from '@app/containers/DynamicContainer';
import { useGetWorkspaceAllSubmissionsQuery } from '@app/store/workspaces/api';

export default function AllSubmissionTab({ workspace_id, requestedForDeletionOnly }: any) {
    const [page, setPage] = useState(0);
    const [total, setTotal] = useState(0);
    const submissionsQuery = useGetWorkspaceAllSubmissionsQuery({
        workspaceId: workspace_id,
        requestedForDeletionOly: requestedForDeletionOnly,
        page: page + 1,
        size: globalConstants.pageSize
    });
    const [responses, setResponses] = useState<any>([]);

    useEffect(() => {
        if (!submissionsQuery?.isLoading && !!submissionsQuery?.data) {
            setResponses(submissionsQuery?.data?.items);
            setTotal(submissionsQuery?.data?.total || 0);
        }
    }, [submissionsQuery?.data]);

    useEffect(() => {
        submissionsQuery.refetch();
    }, [page]);

    const handlePageChange = (event: any, page: number) => {
        setResponses([]);
        setPage(page);
    };

    if (submissionsQuery.isFetching) return <FullScreenLoader />;

    return (
        <DynamicContainer>
            <div className="flex flex-col md:flex-row justify-between w-full">
                <h1 data-testid="all-submissions-renderer" className="text-2xl font-extrabold mb-4">
                    {requestedForDeletionOnly ? 'Total deletion requests' : 'Total Submissions'} ({total})
                </h1>
            </div>
            <SubmissionsGrid responses={responses} requestedForDeletionOnly={requestedForDeletionOnly} />
            {!responses.length && <EmptyFormsView description="No submissions" className="border-[1px] border-gray-100 rounded-b-lg !rounded-t-none border-t-0 shadow" />}

            {Array.isArray(responses) && total > globalConstants.pageSize && <TablePagination component="div" rowsPerPageOptions={[]} rowsPerPage={globalConstants.pageSize} count={total} page={page} onPageChange={handlePageChange} />}
        </DynamicContainer>
    );
}
