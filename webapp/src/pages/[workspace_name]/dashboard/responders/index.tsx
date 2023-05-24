import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import StyledPagination from '@Components/Common/Pagination';
import SearchInput from '@Components/Common/Search/SearchInput';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import EmptyResponse from '@app/components/ui/empty-response';
import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceResponderDto } from '@app/models/dtos/form';
import { useGetWorkspaceAllSubmissionsQuery, useGetWorkspaceRespondersQuery } from '@app/store/workspaces/api';
import { IGetAllSubmissionsQuery } from '@app/store/workspaces/types';

export default function Responders({ workspace }: any) {
    const [query, setQuery] = useState<IGetAllSubmissionsQuery>({
        workspaceId: workspace.id,
        page: 1,
        size: globalConstants.pageSize
    });

    const { data, isLoading, isError } = useGetWorkspaceRespondersQuery(query);

    const { t } = useTranslation();

    const handlePageChange = (e: any, page: number) => {
        setQuery({ ...query, page: page });
    };

    const dataTableResponseColumns: any = [
        {
            name: t(formConstant.responder),
            selector: (responder: WorkspaceResponderDto) => responder.email,
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
            name: t(formConstant.responses),
            selector: (responder: WorkspaceResponderDto) => responder.responses,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        },
        {
            name: t(formConstant.deletionRequests),
            selector: (responder: WorkspaceResponderDto) => responder.deletionRequests,
            style: {
                color: 'rgba(0,0,0,.54)',
                paddingLeft: '16px',
                paddingRight: '16px'
            }
        }
    ];

    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({ ...query, email: event.target.value });
        else {
            const { email, ...removedQuery } = query;
            setQuery(removedQuery);
        }
    };
    const response = () => {
        if (data?.items && data?.items.length > 0)
            return (
                <>
                    <DataTable className="p-0 mt-4" columns={dataTableResponseColumns} data={data?.items || []} customStyles={dataTableCustomStyles} highlightOnHover={false} pointerOnHover={false} />
                    {Array.isArray(data?.items) && (data?.total || 0) > globalConstants.pageSize && (
                        <div className="mt-8 flex justify-center">
                            <StyledPagination shape="rounded" count={data?.total || 0} page={query.page || 1} onChange={handlePageChange} />
                        </div>
                    )}
                </>
            );
        return <EmptyResponse title={t(formConstant.empty.response.title)} description={t(formConstant.empty.response.description)} />;
    };

    return (
        <DashboardLayout>
            {isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {!isLoading && (
                <div className="flex flex-col py-4">
                    <div className="h4">
                        {t(formConstant.responders)} {data && ' (' + data.total + ')'}
                    </div>
                    <div className="w-full md:w-[282px] mt-6">
                        <SearchInput handleSearch={handleSearch} />
                    </div>

                    {response()}
                </div>
            )}
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
