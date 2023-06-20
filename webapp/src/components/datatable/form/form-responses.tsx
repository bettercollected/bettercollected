import React, { useState } from 'react';

import SearchInput from '@Components/Common/Search/SearchInput';

import ResponsesTable from '@app/components/datatable/responses';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';

export default function FormResponsesTable({ props }: any) {
    const { formId, workspace, requestForDeletion } = props;
    const [page, setPage] = useState(1);
    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: requestForDeletion,
        page: page,
        size: globalConstants.pageSize
    });
    const { data, isLoading } = useGetFormsSubmissionsQuery(query);

    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({ ...query, dataOwnerIdentifier: event.target.value });
        else {
            const { dataOwnerIdentifier, ...removedQuery } = query;
            setQuery(removedQuery);
        }
    };

    if (isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    if (data)
        return (
            <>
                <div className="w-full md:w-[282px] my-6">
                    <SearchInput handleSearch={handleSearch} />
                </div>
                <ResponsesTable formId={formId} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={data} />
            </>
        );
    return <></>;
}
