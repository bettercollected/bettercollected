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
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );

    const setShowTabularView = (show: boolean) => {
        setShowTabularResponses(show);
        localStorage.setItem('tabularResponses', String(show));
    };

    return (
        <div>
            <div className={`mb-12 flex flex-col gap-2 lg:flex-row lg:justify-between ${!isSubmission ? '' : 'px-2 md:px-32'}`}>
                <div className="flex flex-col md:w-[660px] lg:gap-2">
                    <p className="body1">{isSubmission ? `${t(formConstant.responders)}` : `${t(formConstant.deletionRequests)}`}</p>
                    <p className="text-black-700 text-sm font-normal ">{isSubmission ? t(formPage.responsesDescription) : t(formPage.deletionRequestDescription)}</p>
                    {environments.ENABLE_EXPORT_CSV && form?.settings?.provider === 'self' && isSubmission && (
                        <AppButton
                            variant={ButtonVariant.Tertiary}
                            onClick={() =>
                                openModal('EXPORT_RESPONSES', {
                                    formId: form.formId
                                })
                            }
                            className={'mt-1 w-1/4'}
                        >
                            Export as CSV{' '}
                        </AppButton>
                    )}
                </div>
                <div className="flex w-full flex-col items-end gap-4 md:w-[282px]">
                    <SearchInput handleSearch={handleSearch} placeholder={t(formPage.searchByEmail)} className="!bg-black-300" />
                    {form?.settings?.provider === 'self' && !requestForDeletion && (
                        <div className="flex w-fit  cursor-pointer overflow-hidden rounded-lg bg-gray-100">
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
