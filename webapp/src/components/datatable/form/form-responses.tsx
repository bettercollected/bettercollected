import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';
import TabularResponses from '@Components/Form/TabularResponses';
import { FormatListBulleted, ViewList } from '@mui/icons-material';

import ResponsesTable from '@app/components/datatable/responses';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { formConstant } from '@app/constants/locales/form';
import { formPage } from '@app/constants/locales/form-page';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';

export default function FormResponsesTable({ props }: any) {
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);

    const { workspace, requestForDeletion, isSubmission = false } = props;
    const [page, setPage] = useState(1);
    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId: form.formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: requestForDeletion,
        page: page,
        size: globalConstants.pageSize
    });
    const { data, isLoading } = useGetFormsSubmissionsQuery(query);

    const [showTabularResponses, setShowTabularResponses] = useState(form?.provider === 'self' && localStorage.getItem('tabularResponses') === 'true');

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

    const setShowTabularView = (show: boolean) => {
        setShowTabularResponses(show);
        localStorage.setItem('tabularResponses', String(show));
    };

    return (
        <div className={!isSubmission ? '' : 'md:px-32 px-2'}>
            <div className="mb-12 flex flex-col lg:flex-row gap-2 lg:justify-between">
                <div className="flex flex-col lg:gap-2 md:w-[660px]">
                    <p className="body1">{isSubmission ? `${t(formConstant.responders)}` : `${t(formConstant.deletionRequests)}`}</p>
                    <p className="text-sm font-normal text-black-700 ">{isSubmission ? t(formPage.responsesDescription) : t(formPage.deletionRequestDescription)}</p>
                </div>
                <div className="w-full md:w-[282px] flex items-end flex-col gap-4">
                    <SearchInput handleSearch={handleSearch} placeholder={t(formPage.searchByEmail)} className="!bg-black-300" />
                    {form?.settings?.provider === 'self' && (
                        <div className="flex bg-gray-100  rounded-lg cursor-pointer overflow-hidden w-fit">
                            <div
                                className={`p-3 ${!showTabularResponses ? 'bg-black-300' : ''}`}
                                onClick={() => {
                                    setShowTabularView(false);
                                }}
                            >
                                <FormatListBulleted height={24} width={24} />
                            </div>
                            <div
                                className={`p-3 ${showTabularResponses ? 'bg-black-300' : ''}`}
                                onClick={() => {
                                    setShowTabularView(true);
                                }}
                            >
                                <ViewList height={24} width={24} />
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {data && showTabularResponses && <TabularResponses form={form} />}

            {data && !showTabularResponses && <ResponsesTable formId={form.formId} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={data} />}
        </div>
    );
}
