'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';

import MembersIcon from '@Components/Common/Icons/Dashboard/Members';
import { FormIcon } from '@Components/Common/Icons/Form/FormIcon';
import { Groups } from '@mui/icons-material';

import BreadcrumbsRenderer from '@app/Components/Form/renderer/breadcrumbs-renderer';
import GroupFormsTab from '@app/Components/group-preview/forms';
import GroupDetailsTab from '@app/Components/group-preview/group-details';
import GroupMembersTab from '@app/Components/group-preview/member';
import DashboardLayout from '@app/Components/sidebar/dashboard-layout';
import Loader from '@app/Components/ui/loader';
import ParamTab, { TabPanel } from '@app/Components/ui/param-tab';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { useAppSelector } from '@app/store/hooks';
import { useGetRespondersGroupQuery, useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function GroupPreviewClient({ groupId }: { groupId: string }) {
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace.id,
        groupId: groupId
    }, { skip: !workspace.id });

    const workspaceForms = useGetWorkspaceFormsQuery<any>({ workspace_id: workspace.id }, { skip: !workspace.id });
    const { t } = useTranslation();

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(localesCommon.respondersAndGroups),
            url: `/${workspace?.workspaceName}/dashboard/responders-groups`
        },
        {
            title: t(groupConstant.groups),
            url: `/${workspace?.workspaceName}/dashboard/responders-groups?view=Groups`
        },
        {
            title: data?.name,
            disabled: true
        }
    ];

    const paramTabs = [
        {
            icon: <Groups />,
            title: t(groupConstant.details),
            path: 'Group Details'
        },
        {
            icon: <MembersIcon />,
            title: t(members.default) + ' (' + (data?.emails?.length ?? 0) + ')',
            path: 'Members'
        },
        {
            icon: <FormIcon />,
            title: t(localesCommon.forms) + ' (' + (data?.forms?.length ?? 0) + ')',
            path: 'Forms'
        }
    ];

    return (
        <DashboardLayout>
            {(isLoading || workspaceForms.isLoading) && (
                <div className="w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {!(isLoading || workspaceForms.isLoading) && data && workspaceForms.data && (
                <div className="flex flex-col -mt-6">
                    <BreadcrumbsRenderer items={breadcrumbsItem} />
                    <ParamTab className="mb-[38px] pb-0" tabMenu={paramTabs}>
                        <TabPanel className="focus:outline-none" key="Group Details">
                            <GroupDetailsTab group={data} />
                        </TabPanel>
                        <TabPanel className="focus:outline-none" key="Members">
                            <GroupMembersTab group={data} workspace={workspace} />
                        </TabPanel>
                        <TabPanel className="focus:outline-none" key="Forms">
                            <GroupFormsTab group={data} workspaceForms={workspaceForms.data?.items} />
                        </TabPanel>
                    </ParamTab>
                </div>
            )}
        </DashboardLayout>
    );
}
