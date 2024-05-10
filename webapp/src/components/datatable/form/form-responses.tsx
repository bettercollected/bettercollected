import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import SearchInput from '@Components/Common/Search/SearchInput';
import TabularResponses from '@Components/Form/TabularResponses';

import { useModal } from '@app/components/modal-views/context';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import globalConstants from '@app/constants/global';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetFormAllSubmissionsQuery, useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import EmptyResponseIcon from '@app/views/atoms/Icons/EmptyResponseIcon';
import { DownloadIcon } from 'lucide-react';
import ResponsesTable from '../responses';
//@ts-ignore
import { CSVLink } from 'react-csv';
import { getFieldsFromV2Form } from '@app/utils/formUtils';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { getAnswerForField } from '@app/utils/formBuilderBlockUtils';
import { StandardFormResponseDto } from '@app/models/dtos/form';

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
    const [trigger, { isLoading: csvLoading }] = useLazyGetFormAllSubmissionsQuery();

    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({ ...query, dataOwnerIdentifier: event.target.value });
        else {
            const { dataOwnerIdentifier, ...removedQuery } = query;
            setQuery(removedQuery);
        }
    };

    const [csvDatas, setCsvDatas] = useState<any>([]);

    const extractFormResponses = (responses: Array<StandardFormResponseDto>) => {
        return responses.map((response: StandardFormResponseDto) => {
            const fieldResponse: Array<number | string> = [response?.dataOwnerIdentifier || '- -'];
            const singleFieldResponses = getFieldsFromV2Form(form).map((field) => field && (getAnswerForField(response, field) ?? ''));
            singleFieldResponses.forEach((response) => fieldResponse.push(response ?? ''));
            return fieldResponse;
        });
    };

    const extractFormFieldTitles = () => {
        const fieldTitles = ['Responder ID'];
        const fieldQuestions = getFieldsFromV2Form(form).map((field) => field && extractTextfromJSON(field));
        fieldQuestions.forEach((qsn) => fieldTitles.push(qsn ?? ''));
        return fieldTitles;
    };

    const handleClickExportCSV = () => {
        if (form.builderVersion === 'v2') {
            trigger({ formId: form.formId, workspaceId: workspace?.id }).then((result) => {
                const fieldTitles = extractFormFieldTitles();
                const responses = result.data && extractFormResponses(result?.data);
                const csv_list = [];
                csv_list.push(fieldTitles);
                responses?.forEach((response) => {
                    csv_list.push(response);
                });
                setCsvDatas(csv_list);
            });
        } else {
            openModal('EXPORT_RESPONSES', {
                formId: form.formId
            });
        }
    };

    useEffect(() => {
        if (csvDatas.length > 0) {
            document.getElementById('csv_link')?.click();
            setCsvDatas([]);
        }
    }, [csvDatas]);

    if (isLoading)
        return (
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );

    return (
        <div>
            <CSVLink data={csvDatas} filename={`${form.title}.csv`} className="btn btn-primary" target="_blank" id="csv_link" />
            {data && Array.isArray(data.items) && data.items.length ? (
                <>
                    <div className={`mb-12 flex flex-col gap-2 px-2 md:px-28 lg:flex-row lg:justify-between`}>
                        <div className="flex w-full flex-row justify-between">
                            <div className="flex w-full flex-row items-center gap-4 ">
                                <SearchInput handleSearch={handleSearch} placeholder={'Search Responses'} className="!bg-black-300 md:w-[282px]" />
                                {/* <Button variant="v2Button">Filter</Button>
                        <Button variant="v2Button">Sort</Button> */}
                            </div>
                            {environments.ENABLE_EXPORT_CSV && form?.settings?.provider === 'self' && isSubmission && (
                                <Button isLoading={form.builderVersion === 'v2' && csvLoading} variant="v2Button" icon={<DownloadIcon className="h-4 w-4" />} onClick={handleClickExportCSV} className={''}>
                                    Export CSV
                                </Button>
                            )}
                        </div>
                    </div>

                    {data && requestForDeletion ? <ResponsesTable formId={form.formId} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={data} /> : <TabularResponses form={form} />}
                </>
            ) : (
                <div className={'flex flex-col items-center gap-2 py-6'}>
                    <EmptyResponseIcon />
                    <span className={'p3-new text-black'}>No {requestForDeletion ? 'Deletion Request' : 'responses'} yet</span>
                    <span className={'p4-new text-black-600'}>This form doesn&apos;t have any {requestForDeletion ? 'Deletion Request' : 'responses'} yet.</span>
                </div>
            )}
        </div>
    );
}
