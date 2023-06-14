import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import { FormIcon } from '@Components/Common/Icons/FormIcon';
import MembersIcon from '@Components/Common/Icons/Members';
import { Groups } from '@mui/icons-material';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import GroupForms from '@app/components/group-preview/forms';
import GroupDetails from '@app/components/group-preview/group-details';
import GroupMembers from '@app/components/group-preview/member';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import Loader from '@app/components/ui/loader';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import { localesCommon } from '@app/constants/locales/common';
import { groupConstant } from '@app/constants/locales/group';
import { members } from '@app/constants/locales/members';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { useAppSelector } from '@app/store/hooks';
import { useGetRespondersGroupQuery, useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';

export async function getServerSideProps(_context: any) {
    const { group_id } = _context.query;
    const authProps = await getAuthUserPropsWithWorkspace(_context);
    return {
        props: {
            ...authProps.props,
            groupId: group_id
        }
    };
}
export default function GroupPreviewPage({ groupId }: { groupId: string }) {
    const router = useRouter();
    const locale = router?.locale === 'en' ? '' : `${router?.locale}/`;
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace.id,
        groupId: groupId
    });
    const workspaceForms = useGetWorkspaceFormsQuery<any>({ workspace_id: workspace.id });
    const { t } = useTranslation();
    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(localesCommon.respondersAndGroups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders`
        },
        {
            title: t(groupConstant.groups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders?view=Groups`
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
            title: t(members.default) + ' (' + data?.emails.length + ')',
            path: 'Members'
        },
        {
            icon: <FormIcon />,
            title: t(localesCommon.forms) + ' (' + data?.forms?.length + ')',
            path: 'Forms'
        }
    ];

    return (
        <DashboardLayout>
            {isLoading && workspaceForms.isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {!isLoading && !workspaceForms.isLoading && data && workspaceForms.data && (
                <div className="flex flex-col -mt-6 ">
                    <BreadcrumbsRenderer items={breadcrumbsItem} />
                    <div className="flex gap-2 items-center ">
                        {/* <ChevronForward className=" h-6 w-6 py-[2px] cursor-pointer px-[3px] rotate-180" /> */}
                        <span className="h4">{t(groupConstant.groups)}</span>
                    </div>
                    <ParamTab className="mb-[38px] mt-[24px]  pb-0 border-b  border-black-500" tabMenu={paramTabs}>
                        <TabPanel className="focus:outline-none" key="Group Details">
                            <GroupDetails group={data} />
                        </TabPanel>
                        <TabPanel className="focus:outline-none" key="Members">
                            <GroupMembers group={data} workspace={workspace} />
                        </TabPanel>
                        <TabPanel className="focus:outline-none" key="Forms">
                            <GroupForms group={data} workspaceForms={workspaceForms.data?.items} />
                        </TabPanel>
                    </ParamTab>
                </div>
            )}
        </DashboardLayout>
    );
}
