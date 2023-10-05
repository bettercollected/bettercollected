import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';

import ResponsesTable from '@app/components/datatable/responses';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { formConstant } from '@app/constants/locales/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';


export default function FormResponsesTable({props}: any) {
    const {t} = useTranslation();
    const form = useAppSelector(selectForm);

    const {workspace, requestForDeletion, isSubmission = false} = props;
    const [page, setPage] = useState(1);
    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId: form.formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: requestForDeletion,
        page: page,
        size: globalConstants.pageSize
    });
    const {data, isLoading} = useGetFormsSubmissionsQuery(query);

    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({...query, dataOwnerIdentifier: event.target.value});
        else {
            const {dataOwnerIdentifier, ...removedQuery} = query;
            setQuery(removedQuery);
        }
    };

    if (isLoading)
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader/>
            </div>
        );
    return (
        <div className={!isSubmission ? "" : "md:px-32 px-2"}>
            <div className="mb-12 flex flex-col lg:flex-row gap-2 lg:justify-between">
                <div className="flex flex-col lg:gap-2">
                    <p className="body1">{isSubmission ? `${t(formConstant.responses)} (${form.responses})` : `${t(formConstant.deletionRequests)} (${form.deletionRequests})`}</p>
                    <p className="text-sm font-normal text-black-700 ">Below, you will find a list of responders who
                        have requested the deletion of their submitted responses.</p>
                </div>
                <div className="w-full md:w-[282px] ">
                    <SearchInput handleSearch={handleSearch} placeholder="Search by Email" className="!bg-black-300"/>
                </div>
            </div>

            {data && <ResponsesTable formId={form.formId} requestForDeletion={requestForDeletion} page={page}
                                     setPage={setPage} submissions={data}/>}
        </div>
    );
}