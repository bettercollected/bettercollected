import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import StyledPagination from '@Components/Common/Pagination';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { formsConstant } from '@app/constants/locales/forms';
import { StandardFormResponseDto, WorkspaceResponderDto } from '@app/models/dtos/form';
import { useGetWorkspaceAllSubmissionsQuery } from '@app/store/workspaces/api';
import { parseDateStrToDate, toHourMinStr, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

export default function Responders({ workspace }: any) {
    const [page, setPage] = useState(0);
    const { data, isLoading, isError } = useGetWorkspaceAllSubmissionsQuery({
        workspaceId: workspace.id,
        data_subjects: true,
        page: page,
        size: globalConstants.pageSize
    });

    const { t } = useTranslation();

    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };

    const dataTableResponseColumns: any = [
        {
            name: t(formsConstant.responder),
            selector: (responder: WorkspaceResponderDto) => responder._id,
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
            name: t(formsConstant.responses),
            selector: (responder: WorkspaceResponderDto) => responder.responses,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(formsConstant.deletionRequests),
            selector: (responder: WorkspaceResponderDto) => responder.deletion_requests,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];

    if (isLoading) {
        return (
            <div className=" w-full py-10 flex justify-center">
                <Loader />
            </div>
        );
    }
    return (
        <DashboardLayout>
            <div className="flex flex-col py-4">
                <div className="h4">Responders {data && ' (' + data.total + ')'}</div>
                <DataTable className="p-0 mt-2" columns={dataTableResponseColumns} data={data?.items || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
                {Array.isArray(data?.items) && (data?.total || 0) > globalConstants.pageSize && (
                    <div className="mt-8 flex justify-center">
                        <StyledPagination shape="rounded" count={data?.total || 0} page={page} onChange={handlePageChange} />
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
