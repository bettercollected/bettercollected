import React, { useState } from 'react';

import { useRouter } from 'next/router';

import StyledPagination from '@Components/Common/Pagination';
import { Typography } from '@mui/material';
import DataTable from 'react-data-table-component';

import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useGetFormsSubmissionsQuery } from '@app/store/workspaces/api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

const responseTableStyles = {
    ...dataTableCustomStyles,
    rows: {
        style: {
            ...dataTableCustomStyles.rows.style,
            border: '1px solid transparent',
            '&:hover': {
                cursor: 'pointer',
                border: '1px solid #0764EB'
            }
        }
    }
};
const ResponsesTable = ({ requestForDeletion, workspaceId, formId }: any) => {
    const [page, setPage] = useState(1);

    const router = useRouter();

    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };

    const { data, isLoading }: any = useGetFormsSubmissionsQuery({
        formId,
        workspaceId: workspaceId,
        requestedForDeletionOly: requestForDeletion,
        page: page + 1,
        size: globalConstants.pageSize
    });

    const [responses, setResponses] = useState<Array<any>>([]);

    const responseDataOwnerField = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <Typography className="!text-black-900 hover:!text-brand-500 cursor-pointer hover:underline" noWrap>
                {response?.dataOwnerIdentifier ?? 'Anonymous'}
            </Typography>
        </div>
    );

    const dataTableResponseColumns: any = [
        {
            name: 'Responder',
            selector: (response: StandardFormResponseDto) => responseDataOwnerField(response),
            grow: 2,
            style: {
                color: '#202124',
                fontSize: '14px',
                fontWeight: 500,
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: 'Submission Date',
            selector: (row: StandardFormResponseDto) => (!!row?.createdAt ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(row.createdAt)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(row.createdAt)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];

    if (!!requestForDeletion) {
        const columnsToAdd = [
            {
                name: 'Response ID',
                selector: (row: StandardFormResponseDto) => row.responseId,
                style: {
                    color: 'rgba(0,0,0,.54)',
                    paddingLeft: '16px',
                    paddingRight: '16px'
                }
            },
            {
                name: 'Status',
                selector: (row: StandardFormResponseDto) => <RequestForDeletionBadge deletionStatus={row?.deletionStatus || 'pending'} />,
                style: {
                    color: 'rgba(0,0,0,.54)',
                    paddingLeft: '16px',
                    paddingRight: '16px'
                }
            }
        ];
        dataTableResponseColumns.splice(1, 0, ...columnsToAdd);
    }

    const onRowClicked = (response: StandardFormResponseDto) => {
        if (!requestForDeletion) {
            if (!requestForDeletion)
                router.push(
                    {
                        pathname: router.pathname,
                        query: { ...router.query, sub_id: response.responseId }
                    },
                    undefined,
                    { scroll: true, shallow: true }
                );
        }
    };

    return (
        <>
            {isLoading ? (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            ) : (
                <>
                    <DataTable
                        className="p-0 mt-2"
                        columns={dataTableResponseColumns}
                        data={data?.items || []}
                        customStyles={requestForDeletion ? dataTableCustomStyles : responseTableStyles}
                        highlightOnHover={false}
                        pointerOnHover={false}
                        onRowClicked={onRowClicked}
                    />
                    {Array.isArray(responses) && data?.total > globalConstants.pageSize && (
                        <div className="mt-8 flex justify-center">
                            <StyledPagination shape="rounded" count={data?.total || 0} page={page} onChange={handlePageChange} />
                        </div>
                    )}
                </>
            )}
        </>
    );
};

export default ResponsesTable;
