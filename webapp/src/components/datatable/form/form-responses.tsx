import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import SearchInput from '@Components/Common/Search/SearchInput';
import TabularResponses from '@Components/Form/TabularResponses';
import { FormatListBulleted, ViewList } from '@mui/icons-material';

import ResponsesTable from '@app/components/datatable/responses';
import { useModal } from '@app/components/modal-views/context';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
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
    const { openModal } = useModal();

    const { workspace, requestForDeletion, isSubmission = false } = props;
    const [page, setPage] = useState(1);
    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId: form.formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: requestForDeletion,
        page: page,
        size: globalConstants.pageSize
    });

    useEffect(() => {
        setQuery({ ...query, page });
    }, [page]);

    const { data, isLoading } = useGetFormsSubmissionsQuery(query);

    const initTabularResponses = !requestForDeletion && form?.settings?.provider === 'self' && (localStorage.getItem('tabularResponses') === 'true' || localStorage.getItem('tabularResponses') === null);

    const [showTabularResponses, setShowTabularResponses] = useState(initTabularResponses);

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
                    {environments.ENABLE_EXPORT_CSV && form?.settings?.provider === 'self' && isSubmission && (
                        <AppButton
                            variant={ButtonVariant.Tertiary}
                            onClick={() =>
                                openModal('EXPORT_RESPONSES', {
                                    formId: form.formId
                                })
                            }
                            className={'w-1/4 mt-1'}
                        >
                            Export as CSV{' '}
                        </AppButton>
                    )}
                </div>
                <div className="w-full md:w-[282px] flex items-end flex-col gap-4">
                    <SearchInput handleSearch={handleSearch} placeholder={t(formPage.searchByEmail)} className="!bg-black-300" />
                    {form?.settings?.provider === 'self' && !requestForDeletion && (
                        <div className="flex bg-gray-100  rounded-lg cursor-pointer overflow-hidden w-fit">
                            <div
                                className={`p-3 ${showTabularResponses ? 'bg-black-300' : ''}`}
                                onClick={() => {
                                    setShowTabularView(true);
                                }}
                            >
                                <ViewList height={24} width={24} />
                            </div>
                            <div
                                className={`p-3 ${!showTabularResponses ? 'bg-black-300' : ''}`}
                                onClick={() => {
                                    setShowTabularView(false);
                                }}
                            >
                                <FormatListBulleted height={24} width={24} />
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