import React, { useState } from 'react';

import ResponsesTable from '@app/components/datatable/responses';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';

export default function FormResponsesTable({ props }: any) {
    const { formId, workspace, requestForDeletion } = props;
    const [page, setPage] = useState(1);
    const submissions = useGetFormsSubmissionsQuery({
        formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: requestForDeletion,
        page: page,
        size: globalConstants.pageSize
    });
    if (submissions?.isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    return <ResponsesTable formId={formId} workspaceId={workspace?.id} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={submissions} />;
}
