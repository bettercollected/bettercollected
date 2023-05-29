import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import StyledPagination from '@Components/Common/Pagination';
import SearchInput from '@Components/Common/Search/SearchInput';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@app/components/datatable/form/datatable-styles';
import UserMore from '@app/components/icons/user-more';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import EmptyResponse from '@app/components/ui/empty-response';
import Loader from '@app/components/ui/loader';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import WorkspaceGroups from '@app/components/workspace-responders/workspace-groups';
import WorkspaceResponses from '@app/components/workspace-responders/workspace-responders';
import globalConstants from '@app/constants/global';
import { formConstant } from '@app/constants/locales/form';
import { WorkspaceResponderDto } from '@app/models/dtos/form';
import { useGetWorkspaceAllSubmissionsQuery, useGetWorkspaceRespondersQuery } from '@app/store/workspaces/api';
import { IGetAllSubmissionsQuery } from '@app/store/workspaces/types';

export default function Responders({ workspace }: any) {
    const { t } = useTranslation();

    const paramTabs = [
        {
            title: 'All Responders',
            path: 'All Responders'
        },
        {
            title: 'Groups',
            path: 'Groups'
        }
    ];

    return (
        <DashboardLayout>
            <div className="flex flex-col py-4">
                <div className="h4">{t(formConstant.responders)}</div>
                <ParamTab className="my-10  pb-0 border-b  border-black-500" tabMenu={paramTabs}>
                    <TabPanel className="focus:outline-none" key="All Responders">
                        <WorkspaceResponses workspace={workspace} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="Groups">
                        <WorkspaceGroups />
                    </TabPanel>
                </ParamTab>
            </div>
        </DashboardLayout>
    );
}

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
