import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import MembersIcon from '@Components/Common/Icons/Members';

import Collaborators from '@app/components/member/collaborators';
import Invitations from '@app/components/member/invitations';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageMembers({ workspace }: any) {
    const { t } = useTranslation();
    const { workspaceName } = useAppSelector(selectWorkspace);
    const paramTabs = [
        {
            icon: <MembersIcon />,
            title: t(members.collaborators.default),
            path: 'Collaborators'
        },
        {
            icon: <MembersIcon />,
            title: t(members.pendingRequests.default),
            path: 'Pending Requests'
        }
    ];
    return (
        <DashboardLayout boxClassName="px-5 pt-10 lg:px-10">
            <NextSeo title={t(members.default) + ' | ' + workspaceName} noindex={true} nofollow={true} />
            <div className="flex justify-between">
                <div className="h4">{t(members.default)}</div>
            </div>
            <ParamTab className="mb-[38px] mt-[24px] pb-0 " tabMenu={paramTabs}>
                <TabPanel className="focus:outline-none" key="Collaborators">
                    <Collaborators />
                </TabPanel>
                <TabPanel className="focus:outline-none" key="Pending Requests">
                    <Invitations />
                </TabPanel>
            </ParamTab>
        </DashboardLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
