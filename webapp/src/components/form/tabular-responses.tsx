import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import StyledPagination from '@Components/common/pagination';
import cn from 'classnames';
import DataTable from 'react-data-table-component';
import { Shield as ShieldIcon } from 'lucide-react';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import globalConstants from '@app/constants/global';
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery, useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import { downloadFile } from '@app/utils/file-utils';
import { getAnswerForField, getFormFields, getTitleForHeader } from '@app/utils/form-builder-block-utils';
import { dataTableCustomStyles } from '@Components/datatable/datatable-styles';
import { ExpandIcon } from '@Components/icons/expanded-icon';

/**
 * ONE table for the responders view. The previous implementation faked frozen
 * columns with two independent DataTables side by side — their row heights
 * were never guaranteed equal (the identifier cell is two lines, answers are
 * one), so rows drifted out of alignment within a screenful. Here the leading
 * columns (checkbox · expand · Responder ID) are frozen with position:sticky
 * inside the single scroll container (see .responders-frozen-table in
 * globals.css), so alignment holds by construction and the whole row shares
 * one hover + click behaviour.
 */
const customTableStyles = {
    ...dataTableCustomStyles,
    rows: {
        ...dataTableCustomStyles.rows,
        style: {
            ...dataTableCustomStyles.rows.style,
            // Two-line cells (identifier + timestamp) must be allowed to size
            // the row — a forced 48px height is exactly what caused the old
            // misalignment.
            height: 'auto',
            minHeight: '56px',
            cursor: 'pointer'
        }
    }
};

interface TabularResponsesProps {
    form: StandardFormDto;
}

export default function TabularResponses({ form }: TabularResponsesProps) {
    const { toast } = useToast();
    const { openModal } = useFullScreenModal();
    const workspace = useAppSelector(selectWorkspace);
    const [page, setPage] = useState(1);

    const [triggerSingleResponse] = useLazyGetWorkspaceSubmissionQuery();

    const { t } = useTranslation();

    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId: form.formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: false,
        page: page,
        size: globalConstants.pageSize
    });

    useEffect(() => {
        setTimeout(() => setQuery({ ...query, page: page }), 0);
    }, [page]);

    const downloadFormFile = async (ans: any) => {
        try {
            if (!ans?.file_metadata?.url) return;
            downloadFile(ans?.file_metadata?.url, ans?.file_metadata.name ?? ans?.file_metadata.id);
        } catch (err) {
            toast({ description: 'Error downloading file', variant: 'destructive' });
        }
    };

    const getAnswerField = (response: StandardFormResponseDto, field: StandardFormFieldDto) => {
        if (field.type === FieldTypes.FILE_UPLOAD || field.type === FieldTypes.INPUT_FILE_UPLOAD) {
            const ans = response.answers[field.id];
            return (
                <div
                    onClick={(event) => {
                        event.stopPropagation();
                        downloadFormFile(ans);
                    }}
                    className={cn('!text-black-600 p2-new w-[180px] cursor-default truncate rounded px-2 py-1', ans?.file_metadata?.url ? 'bg-black-300 active:bg-black-400 !cursor-pointer' : '')}
                >
                    {getAnswerForField(response, field)}
                </div>
            );
        }
        return <div className={cn('!text-black-600 p2-new w-[180px] truncate')}>{getAnswerForField(response, field)}</div>;
    };

    const responseDataOwnerField = (response: StandardFormResponseDto) => (
        <div aria-hidden className="flex w-fit flex-col gap-1 ">
            {response?.dataOwnerIdentifier ? (
                <p className={cn('!text-black-800 p2-new w-fit max-w-[200px] truncate')}>{response.dataOwnerIdentifier}</p>
            ) : (
                // Anonymity is the product's promise — show it as a state, not
                // as missing data ("- -").
                <span className="flex w-fit items-center gap-1 rounded-full bg-[#E7F4EE] px-2 py-0.5 text-xs font-medium text-[#0E8A5F]">
                    <ShieldIcon className="h-3 w-3" strokeWidth={2} />
                    Anonymous
                </span>
            )}
            <span className="text-black-600 text-[10px] font-normal">{utcToLocalDateTIme(response?.createdAt)}</span>
        </div>
    );

    function getTitleForHeaderForTable(field: StandardFormFieldDto) {
        const title = getTitleForHeader(field, form);
        return (
            <span title={title} className="p3-new !text-black-800 w-[180px] truncate">
                {title}
            </span>
        );
    }

    const openResponse = (response: StandardFormResponseDto) => {
        triggerSingleResponse({
            workspace_id: workspace?.id ?? '',
            submission_id: response.responseId
        }).then((result: any) => {
            openModal('VIEW_RESPONSE', { response: result.data.response, formFields: getFormFields(result.data.form), form: result.data.form, formId: result.data.form.formId, workspaceId: workspace.id });
        });
    };

    const cellStyle = {
        color: 'rgba(0,0,0,.54)',
        paddingLeft: '8px',
        paddingRight: '8px',
        height: 'auto',
        overflow: 'hidden'
    };

    const columns: any = [
        {
            name: '',
            cell: (response: StandardFormResponseDto) => (
                <ExpandIcon
                    onClick={(event: any) => {
                        event.stopPropagation();
                        openResponse(response);
                    }}
                />
            ),
            style: { ...cellStyle, cursor: 'pointer' },
            width: '40px',
            minWidth: '0px'
        },
        {
            name: t('FORM.RESPONDER') + ' ID',
            cell: (response: StandardFormResponseDto) => responseDataOwnerField(response),
            style: cellStyle,
            width: '224px'
        },
        ...getFormFields(form).map((field: any) => ({
            name: getTitleForHeaderForTable(field),
            selector: (response: StandardFormResponseDto) => getAnswerField(response, field),
            style: cellStyle,
            width: '200px'
        }))
    ];

    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };
    const { data } = useGetFormsSubmissionsQuery(query, { skip: !workspace.id });

    return (
        <>
            {Array.isArray(data?.items) && (
                <div className="responders-frozen-table border-black-300 overflow-hidden rounded-lg border">
                    <DataTable onRowClicked={openResponse} columns={columns} selectableRows customStyles={customTableStyles} data={data?.items || []} fixedHeader fixedHeaderScrollHeight="65vh" />
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
