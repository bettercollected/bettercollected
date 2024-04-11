import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import StyledPagination from '@Components/Common/Pagination';
import { Typography } from '@mui/material';
import cn from 'classnames';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import globalConstants from '@app/constants/global';
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import { downloadFile } from '@app/utils/fileUtils';
import { convertPlaceholderToDisplayValue, getAnswerForField } from '@app/utils/formBuilderBlockUtils';

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

    const getResponseForFileUploadField = (response: StandardFormResponseDto, field: StandardFormFieldDto) => {
        const answer = response.answers[field.id];

        return (
            <span className="p1 flex w-full cursor-pointer items-center justify-between rounded bg-blue-200 px-3 py-2" onClick={downloadFormFile}>
                <span className="mr-5 flex-1 truncate">{answer?.file_metadata?.name}</span>
                <span className="text-sm">{answer?.file_metadata?.size} MB</span>
            </span>
        );
    };

    const getAnswerField = (response: StandardFormResponseDto, field: any) => {
        return (
            <>
                <Typography className={cn('!text-black-900 body3 ')} noWrap>
                    {field.type === FieldTypes.FILE_UPLOAD || field.type === FormBuilderTagNames.INPUT_FILE_UPLOAD ? getResponseForFileUploadField(response, field) : getAnswerForField(response, field)}
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

    const IgnoredResponsesFieldType = [FieldTypes.TEXT, null];

    function getFormFields() {
        if (form.builderVersion === 'v2') {
            const fields = form.fields.map((slide) => {
                return slide?.properties?.fields?.filter((field: StandardFormFieldDto) => !IgnoredResponsesFieldType.includes(field.type));
            });
            return fields.flat();
        } else {
            return getFilteredInputFields();
        }
    }

    function getTitleForHeader(field: StandardFormFieldDto) {
        if (form.builderVersion === 'v2') {
            return field.title;
        } else {
            convertPlaceholderToDisplayValue(
                form?.fields.map((field: any, index: number) => {
                    return {
                        ...field,
                        position: index
                    };
                }) ?? [],
                field?.value || ''
            );
        }
    }

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
        ...getFormFields().map((field: any) => {
            return {
                name: getTitleForHeader(field),
                selector: (response: StandardFormResponseDto) => getAnswerField(response, field),
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
    console.log('form responses : ', data, form);

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
