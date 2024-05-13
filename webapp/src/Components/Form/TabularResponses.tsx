import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import StyledPagination from '@Components/Common/Pagination';
import { Typography } from '@mui/material';
import cn from 'classnames';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import globalConstants from '@app/constants/global';
import { StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import { utcToLocalDateTIme } from '@app/utils/dateUtils';
import { downloadFile } from '@app/utils/fileUtils';
import { convertPlaceholderToDisplayValue, getAnswerForField } from '@app/utils/formBuilderBlockUtils';
import { getFieldsFromV2Form } from '@app/utils/formUtils';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { ExpandIcon } from '@app/views/atoms/Icons/ExpandIcon';

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

const customTableStylesForResponderDetails = {
    ...dataTableCustomStyles,
    table: {
        ...dataTableCustomStyles.table,
        style: {
            ...dataTableCustomStyles.table.style,
            borderRight: '1px solid #DBDBDB',
            boxShadow: '2px 0px 4px 0px rgba(0, 0, 0, 0.15)'
        }
    }
};

interface TabularResponsesProps {
    form: StandardFormDto;
}

export default function TabularResponses({ form }: TabularResponsesProps) {
    const router = useRouter();
    const { openModal } = useFullScreenModal();
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
                    fieldId: field.id,
                    id: field.id
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

    const getAnswerField = (response: StandardFormResponseDto, field: any) => {
        return (
            <>
                <Typography className={cn('!text-black-600 p2-new  w-[140px] truncate')} noWrap>
                    {getAnswerForField(response, field)}
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
        <div aria-hidden className="flex w-fit flex-col gap-1 ">
            <Typography className={cn('!text-black-800 p2-new w-fit truncate')} noWrap>
                {response?.dataOwnerIdentifier || '- -'}
            </Typography>
            <span className="text-black-600 text-[10px] font-normal">{utcToLocalDateTIme(response?.createdAt)}</span>
        </div>
    );

    function getFormFields() {
        if (form.builderVersion === 'v2') {
            return getFieldsFromV2Form(form);
        } else {
            return getFilteredInputFields();
        }
    }

    function getTitleForHeader(field: StandardFormFieldDto) {
        let title: string = '';
        if (form.builderVersion === 'v2') {
            title = extractTextfromJSON(field);
        } else {
            title = convertPlaceholderToDisplayValue(
                form?.fields.map((field: any, index: number) => {
                    return {
                        ...field,
                        position: index
                    };
                }) ?? [],
                field?.value || ''
            );
        }
        return <span className="p3-new !text-black-800 truncate md:w-[250px]">{title}</span>;
    }

    function getColumnForExpandIcon(response: StandardFormResponseDto) {
        return (
            <ExpandIcon
                onClick={() => {
                    openModal('VIEW_RESPONSE', { response: response, formFields: getFormFields(), formId: form.formId, workspaceId: workspace.id });
                }}
            />
        );
    }

    const columnsForResponderDetail: any = [
        {
            name: '',
            cell: (response: StandardFormResponseDto) => getColumnForExpandIcon(response),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '8px',
                height: 'auto',
                overflow: 'hidden ',
                paddingRight: '8px',
                textOverFlow: 'ellipsis',
                cursor: 'pointer'
            },
            width: '40px',
            minWidth: '0px'
        },
        {
            name: t('FORM.RESPONDER') + ' ID',
            cell: (response: StandardFormResponseDto) => responseDataOwnerField(response),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '8px',
                height: 'auto',
                overflow: 'hidden ',
                paddingRight: '8px',
                textOverFlow: 'ellipsis'
            },
            ignoreRowClick: true
        }
    ];

    const columnForResponseData: any = [
        ...getFormFields().map((field: any) => {
            return {
                name: getTitleForHeader(field),
                className: '!bg-red-100',
                selector: (response: StandardFormResponseDto) => getAnswerField(response, field),
                style: {
                    color: 'rgba(0,0,0,.54)',
                    paddingLeft: '8px',
                    height: 'auto',
                    overflow: 'hidden ',
                    paddingRight: '8px'
                },
                width: '156px !important'
            };
        })
    ];

    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };
    const { data, isLoading } = useGetFormsSubmissionsQuery(query, { skip: !workspace.id });

    const onClickExpandSingleResponse = (response: StandardFormResponseDto) => {
        openModal('VIEW_RESPONSE', { response: response, formFields: getFormFields(), formId: form.formId, workspaceId: workspace.id });
    };

    return (
        <>
            {Array.isArray(data?.items) && (
                <div className="flex flex-row">
                    {data?.items.length ? (
                        <div className="flex-1">
                            <DataTable onRowClicked={onClickExpandSingleResponse} columns={columnsForResponderDetail} selectableRows customStyles={customTableStylesForResponderDetails} data={data?.items || []} />
                        </div>
                    ) : (
                        <></>
                    )}
                    <DataTable onRowClicked={onRowClicked} columns={columnForResponseData} customStyles={customTableStyles} data={data?.items || []} />
                </div>
            )}
            {Array.isArray(data?.items) && (data?.total || 0) > globalConstants.pageSize && (
                <div className="mt-8 flex justify-center">
                    <StyledPagination shape="rounded" count={data?.pages || 0} page={page} onChange={handlePageChange} />
                </div>
            )}
        </>
    );
}
