import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import { Typography } from '@mui/material';
import TablePagination from '@mui/material/TablePagination';
import DataTable from 'react-data-table-component';

import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import globalConstants from '@app/constants/global';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useGetFormsSubmissionsQuery, useGetWorkspaceSubmissionsQuery } from '@app/store/workspaces/api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

const ResponsesTable = ({ requestForDeletion, workspaceId, formId }: any) => {
    const [page, setPage] = useState(0);

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
        <div
            aria-hidden
            onClick={() => {
                if (!requestForDeletion)
                    router.push(
                        {
                            pathname: router.pathname,
                            query: { ...router.query, sub_id: response.responseId }
                        },
                        undefined,
                        { scroll: true, shallow: true }
                    );
            }}
            className="w-fit"
        >
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

    return (
        <>
            <DataTable className="p-0 mt-2" columns={dataTableResponseColumns} data={data?.items || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
            {Array.isArray(responses) && data?.total > globalConstants.pageSize && <TablePagination component="div" rowsPerPageOptions={[]} rowsPerPage={globalConstants.pageSize} count={data?.total || 0} page={page} onPageChange={handlePageChange} />}
        </>
    );
};

export default ResponsesTable;
