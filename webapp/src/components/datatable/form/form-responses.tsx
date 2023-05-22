import React, { useState } from 'react';

import ResponsesTable from '@app/components/datatable/responses';
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

    return <ResponsesTable formId={formId} workspaceId={workspace?.id} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={submissions} />;
}
