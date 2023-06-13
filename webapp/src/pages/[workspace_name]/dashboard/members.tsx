import { useTranslation } from 'next-i18next';

import MembersIcon from '@Components/Common/Icons/Members';

import Collaborators from '@app/components/member/collaborators';
import Invitations from '@app/components/member/invitations';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import { members } from '@app/constants/locales/members';
import { selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';

export default function ManageMembers({ workspace }: any) {
    const isProPlan = useAppSelector(selectIsProPlan);
    const { t } = useTranslation();
    const paramTabs = [
        {
            icon: <MembersIcon />,
            title: t(members.collaborators.default),
            path: 'Collaborators'
        }
    ];
    if (isProPlan) {
        paramTabs.push({
            icon: <MembersIcon />,
            title: t(members.pendingRequests.default),
            path: 'Pending Requests'
        });
    }
    return (
        <DashboardLayout>
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
