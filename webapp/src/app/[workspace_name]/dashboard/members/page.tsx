"use client";

import { useTranslation } from 'next-i18next';

import MembersIcon from '@Components/Common/Icons/Dashboard/Members';

import Collaborators from '@app/Components/member/collaborators';
import Invitations from '@app/Components/member/invitations';
import ParamTab, { TabPanel } from '@app/Components/ui/param-tab';
import { members } from '@app/constants/locales/members';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageMembers() {
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
        <div className="flex flex-col">
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
        </div>
    );
}
