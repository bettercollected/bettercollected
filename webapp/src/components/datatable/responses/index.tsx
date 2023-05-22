import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import StyledPagination from '@Components/Common/Pagination';
import { Typography } from '@mui/material';
import cn from 'classnames';
import DataTable from 'react-data-table-component';

import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import EmptyResponse from '@app/components/ui/empty-response';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { formsConstant } from '@app/constants/locales/forms';
import { localesGlobal } from '@app/constants/locales/global';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { useGetFormsSubmissionsQuery, useGetWorkspaceAllSubmissionsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
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
const ResponsesTable = ({ requestForDeletion, submissions, workspaceId, formId, page, setPage }: any) => {
    const router = useRouter();
    const workspaceStats = useGetWorkspaceStatsQuery(workspaceId, { pollingInterval: 30000 });

    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };
    const { t } = useTranslation();

    const [responses, setResponses] = useState<Array<any>>([]);

    const responseDataOwnerField = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <Typography className={cn('!text-black-900 body3 ', !requestForDeletion && 'hover:!text-brand-500 cursor-pointer hover:underline')} noWrap>
                {response?.dataOwnerIdentifier ?? 'Anonymous'}
            </Typography>
        </div>
    );
    const responseFormTitle = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <Typography className="!text-black-900 body3 " noWrap>
                {response?.formTitle ?? 'Untitled'}
            </Typography>
        </div>
    );

    const dataTableResponseColumns: any = [
        {
            name: t(formsConstant.requestedBy),
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
            name: t(formsConstant.submissionDate),
            selector: (row: StandardFormResponseDto) => (!!row?.createdAt ? `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(row.createdAt)))} ${toHourMinStr(parseDateStrToDate(utcToLocalDate(row.createdAt)))}` : ''),
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                fontSize: '16px',
                lineheight: '24px',
                paddingRight: '16px'
            }
        }
    ];

    if (!!requestForDeletion) {
        const statusToAdd = [
            {
                name: t(localesGlobal.status),
                selector: (row: StandardFormResponseDto) => <RequestForDeletionBadge deletionStatus={row?.deletionStatus || t(formsConstant.status.pending)} />,
                style: {
                    color: 'rgba(0,0,0,.54)',
                    paddingLeft: '16px',
                    paddingRight: '16px'
                }
            }
        ];
        dataTableResponseColumns.splice(3, 0, ...statusToAdd);
    }
    if (!formId) {
        const formToAdd = [
            {
                name: t(localesGlobal.form),
                selector: (response: StandardFormResponseDto) => responseFormTitle(response),
                style: {
                    color: '#202124',
                    fontSize: '14px',
                    fontWeight: 500,
                    paddingLeft: '16px',
                    paddingRight: '16px'
                }
            }
        ];
        dataTableResponseColumns.splice(1, 0, ...formToAdd);
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
            {submissions?.isLoading ? (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            ) : (
                submissions?.data?.items &&
                (submissions?.data?.items.length > 0 ? (
                    <>
                        {!formId && (
                            <p className="body1 text-black-900 my-10">
                                {workspaceStats?.data?.deletion_requests.pending || 0}/{workspaceStats?.data?.deletion_requests.total} {t(localesGlobal.deletionRemaining)}
                            </p>
                        )}
                        <DataTable
                            className="p-0 mt-2 h-full !overflow-visible"
                            columns={dataTableResponseColumns}
                            data={submissions?.data?.items || []}
                            customStyles={requestForDeletion ? dataTableCustomStyles : responseTableStyles}
                            highlightOnHover={false}
                            pointerOnHover={false}
                            onRowClicked={onRowClicked}
                        />
                        {Array.isArray(responses) && submissions?.data?.total > globalConstants.pageSize && (
                            <div className="mt-8 flex justify-center">
                                <StyledPagination shape="rounded" count={submissions?.data?.total || 0} page={page} onChange={handlePageChange} />
                            </div>
                        )}
                    </>
                ) : (
                    <EmptyResponse
                        title={t(requestForDeletion ? formsConstant.empty.deletionRequest.title : formsConstant.empty.response.title)}
                        description={t(requestForDeletion ? formsConstant.empty.deletionRequest.description : formsConstant.empty.response.description)}
                    />
                ))
            )}
        </>
    );
};

export default ResponsesTable;
