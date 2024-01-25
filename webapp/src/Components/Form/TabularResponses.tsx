import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import StyledPagination from '@Components/Common/Pagination';
import { Typography } from '@mui/material';
import cn from 'classnames';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import globalConstants from '@app/constants/global';
import { StandardFormDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import { downloadFile } from '@app/utils/fileUtils';
import { convertPlaceholderToDisplayValue } from '@app/utils/formBuilderBlockUtils';

const customTableStyles = {
    ...dataTableCustomStyles,
    rows: {
        ...dataTableCustomStyles.rows,
        style: {
            ...dataTableCustomStyles.rows.style,
            cursor: 'pointer'
        }
    }
};

interface TabularResponsesProps {
    form: StandardFormDto;
}

export default function TabularResponses({ form }: TabularResponsesProps) {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const [page, setPage] = useState(1);

    const { t } = useTranslation();

    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId: form.formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: false,
        page: page,
        size: globalConstants.pageSize
    });

    useEffect(() => {
        setQuery({ ...query, page: page });
    }, [page]);

    const getFilteredInputFields = () => {
        const filteredFields: Array<any> = [];
        form?.fields.forEach((field, index) => {
            if (field.type.includes('input_')) {
                const x: any = {
                    fieldId: field.id
                };
                const previousField = form?.fields[index - 1] || undefined;
                let text = field?.properties?.placeholder;
                if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                    text = previousField?.value;
                }
                x.value = text;
                x.type = field.type;
                x.properties = field?.properties;
                filteredFields.push(x);
            }
        });
        return filteredFields;
    };

    const downloadFormFile = async (ans: any) => {
        try {
            downloadFile(ans?.file_metadata?.url, ans?.file_metadata.name ?? ans?.file_metadata.id);
        } catch (err) {
            toast('Error downloading file', { type: 'error' });
        }
    };

    const getAnswerForField = (response: StandardFormResponseDto, inputField: any) => {
        const answer = response.answers[inputField.fieldId];
        switch (inputField.type) {
            case FormBuilderTagNames.INPUT_RATING:
            case FormBuilderTagNames.INPUT_NUMBER:
                return answer?.number;
            case FormBuilderTagNames.INPUT_SHORT_TEXT:
            case FormBuilderTagNames.INPUT_LONG_TEXT:
                return answer?.text;
            case FormBuilderTagNames.INPUT_LINK:
                return answer?.url;
            case FormBuilderTagNames.INPUT_EMAIL:
                return answer?.email;
            case FormBuilderTagNames.INPUT_DATE:
                return answer?.date;
            case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            case FormBuilderTagNames.INPUT_DROPDOWN:
                const compareValue = !answer?.choice?.value?.match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$');
                if (compareValue) {
                    return inputField?.properties?.choices.find((choice: any) => choice.value === answer?.choice?.value)?.value;
                }
                return inputField?.properties?.choices?.find((choice: any) => choice.id === answer?.choice?.value)?.value;
            case FormBuilderTagNames.INPUT_CHECKBOXES:
                const choicesAnswers = answer?.choices?.values;
                const compareIds = Array.isArray(choicesAnswers) && choicesAnswers.length > 0 && choicesAnswers?.every((choice: any) => choice.match('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'));
                if (!compareIds) {
                    const choices = inputField?.properties?.choices?.filter((choice: any) => answer?.choices?.values?.includes(choice.value));
                    return choices?.map((choice: any) => choice.value)?.join(', ');
                }
                const choices = inputField?.properties?.choices?.filter((choice: any) => answer?.choices?.values?.includes(choice.id));
                return choices?.map((choice: any) => choice.value)?.join(', ');
            case FormBuilderTagNames.INPUT_PHONE_NUMBER:
                return answer?.phone_number;

            case FormBuilderTagNames.INPUT_RANKING:
                return answer?.choices?.values?.map((choice: any) => choice?.value)?.join(', ');
            case FormBuilderTagNames.INPUT_FILE_UPLOAD:
                return (
                    <span className="p1 flex w-full justify-between items-center rounded bg-blue-200 py-2 px-3 cursor-pointer" onClick={downloadFormFile}>
                        <span className="flex-1 truncate mr-5">{answer?.file_metadata?.name}</span>
                        <span className="text-sm">{answer?.file_metadata?.size} MB</span>
                    </span>
                );
            default:
                return '';
        }
    };

    const getAnswerField = (response: StandardFormResponseDto, inputField: any) => {
        return (
            <>
                <Typography className={cn('!text-black-900 body3 ')} noWrap>
                    {getAnswerForField(response, inputField)}
                </Typography>
            </>
        );
    };

    const onRowClicked = (response: StandardFormResponseDto) => {
        router.push(
            {
                pathname: router.pathname,
                query: { ...router.query, sub_id: response.responseId }
            },
            undefined,
            { scroll: true, shallow: true }
        );
    };

    const responseDataOwnerField = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <Typography className={cn('!text-black-900 body3 ')} noWrap>
                {response?.dataOwnerIdentifier || 'Anonymous'}
            </Typography>
        </div>
    );

    const columns: any = [
        {
            name: t('FORM.RESPONDER'),
            cell: (response: StandardFormResponseDto) => responseDataOwnerField(response),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                height: 'auto',
                background: '#F7F8FA',
                opacity: 100,
                zIndex: 100,
                width: '400px !important',
                overflow: 'hidden ',
                paddingRight: '16px'
            }
        },
        ...getFilteredInputFields().map((inputField: any) => {
            return {
                name: convertPlaceholderToDisplayValue(
                    form?.fields.map((field: any, index: number) => {
                        return {
                            ...field,
                            position: index
                        };
                    }) ?? [],
                    inputField?.value || ''
                ),
                selector: (response: StandardFormResponseDto) => getAnswerField(response, inputField),
                style: {
                    color: 'rgba(0,0,0,.54)',
                    paddingLeft: '16px',
                    height: 'auto',
                    width: '400px !important',
                    overflow: 'hidden ',
                    paddingRight: '16px'
                }
            };
        })
    ];

    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };
    const { data, isLoading } = useGetFormsSubmissionsQuery(query, { skip: !workspace.id });

    return (
        <>
            {Array.isArray(data?.items) && <DataTable onRowClicked={onRowClicked} columns={columns} customStyles={customTableStyles} data={data?.items || []} />}
            {Array.isArray(data?.items) && (data?.total || 0) > globalConstants.pageSize && (
                <div className="mt-8 flex justify-center">
                    <StyledPagination shape="rounded" count={data?.pages || 0} page={page} onChange={handlePageChange} />
                </div>
            )}
        </>
    );
}
