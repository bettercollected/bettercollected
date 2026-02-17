"use client";
import { groupConstant } from "@app/constants/locales/group";
import { workspaceConstant } from "@app/constants/locales/workspace";
import { useAppSelector } from "@app/store/hooks";
import { selectWorkspace } from "@app/store/workspaces/slice";
import ResponderIcon from "@app/views/atoms/Icons/Responder";
import UserMore from "@app/views/atoms/Icons/UserMore";
import ParamTab, { TabPanel } from "@Components/ui/param-tab";
import WorkspaceGroups from "@Components/workspace-responders/workspace-groups";
import WorkspaceResponses from "@Components/workspace-responders/workspace-responders";
import { useTranslation } from "next-i18next";

export default function Page() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const paramTabs = [
        {
            icon: <ResponderIcon className="w-10 h-10" />,
            title: t(workspaceConstant.allResponders),
            path: 'All Responders'
        },
        {
            icon: <UserMore className="w-10 h-10" />,
            title: t(groupConstant.groups),
            path: 'Groups'
        }
    ];

    return <div className="flex flex-col">
        <ParamTab className="mb-[30px] py-0" tabMenu={paramTabs}>
            <TabPanel className="focus:outline-none" key="All Responders">
                <WorkspaceResponses workspace={workspace} />
            </TabPanel>
            <TabPanel className="focus:outline-none" key="Groups">
                <WorkspaceGroups workspace={workspace} />
            </TabPanel>
        </ParamTab>
    </div>
}