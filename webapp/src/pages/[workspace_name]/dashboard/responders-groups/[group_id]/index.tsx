import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import { FormIcon } from '@Components/Common/Icons/FormIcon';
import MembersIcon from '@Components/Common/Icons/Members';
import { Groups } from '@mui/icons-material';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import GroupFormsTab from '@app/components/group-preview/forms';
import GroupDetailsTab from '@app/components/group-preview/group-details';
import GroupMembersTab from '@app/components/group-preview/member';
import Back from '@app/components/icons/back';
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
import { selectWorkspace } from '@app/store/workspaces/slice';

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
    const workspace: WorkspaceDto = useAppSelector(selectWorkspace);
    const { data, isLoading } = useGetRespondersGroupQuery({
        workspaceId: workspace.id,
        groupId: groupId
    });
    const workspaceForms = useGetWorkspaceFormsQuery<any>({ workspace_id: workspace.id });
    const { t } = useTranslation();
    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: t(localesCommon.respondersAndGroups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders-groups`
        },
        {
            title: t(groupConstant.groups),
            url: `/${locale}${workspace?.workspaceName}/dashboard/responders-groups?view=Groups`
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
            <NextSeo title={data?.name + ' | ' + workspace.workspaceName} noindex={true} nofollow={true} />;
            {isLoading && workspaceForms.isLoading && (
                <div className=" w-full py-10 flex justify-center">
                    <Loader />
                </div>
            )}
            {!isLoading && !workspaceForms.isLoading && data && workspaceForms.data && (
                <div className="flex flex-col -mt-6 ">
                    <BreadcrumbsRenderer items={breadcrumbsItem} />
                    <div className="flex gap-2 items-center ">
                        <Back onClick={() => router.push(`/${workspace?.workspaceName}/dashboard/responders-groups?view=Groups`)} className="cursor-pointer" />
                        <span className="h4">{t(groupConstant.groups)}</span>
                    </div>
                    <ParamTab className="mb-[38px] mt-6  pb-0 " tabMenu={paramTabs}>
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
