'use client';

import { useTranslation } from 'next-i18next';

import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';

import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import WorkspaceDashboardPinnedForms from '@app/components/workspace-dashboard/workspace-dashboard-pinned-forms';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import WorkspaceDetailsCard from '@Components/RespondersPortal/WorkspaceDetailsCard';
import EditIcon from '@app/views/atoms/Icons/Edit';
import OpenLinkIcon from '@app/views/atoms/Icons/OpenLink';
import { Button } from '@app/shadcn/components/ui/button';
import { ProLogo } from '@app/components/ui/logo';
import { toast } from 'react-toastify';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { getWorkspaceShareURL } from '@app/utils/workspaceUtils';

export default function CreatorDashboard({ hasCustomDomain, ...props }: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { t } = useTranslation();

    const workspace = useAppSelector(selectWorkspace);

    const { openBottomSheetModal } = useBottomSheetModal();

    const pinnedFormsQuery = {
        workspace_id: props.workspace.id,
        pinned_only: true
    };

    const pinnedFormsResponse = useGetWorkspaceFormsQuery(pinnedFormsQuery, { skip: !workspace.id });
    const pinnedForms = pinnedFormsResponse?.data?.items || [];

    return (
        <DashboardLayout boxClassName="bg-black-100" dashboardContentClassName="flex flex-col md:flex-row p-6 gap-4">
            {environments.ENABLE_JOYRIDE_TOURS && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_DASHBOARD_OVERVIEW}
                    scrollOffset={68}
                    placement="bottom-end"
                    steps={[
                        {
                            title: <JoyrideStepTitle text="Your workspace profile and title" />,
                            content: <JoyrideStepContent>This is your workspace profile image and title. You can later change this in &quot;Manage workspace&quot; settings page.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_INFO}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Workspace Collaborators" />,
                            content: <JoyrideStepContent>Invite others to collaborate on your workspace.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_COLLABORATORS}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },

                        {
                            title: <JoyrideStepTitle text="Share your workspace" />,
                            content: <JoyrideStepContent>Share your workspace in different social media platforms, or copy the link via &quot;Share&quot; button.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_SHARE}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Preview your public workspace" />,
                            content: (
                                <JoyrideStepContent>
                                    This link navigates you to your public workspace portal. <br /> <br /> Public workspace portal can be viewed by everyone.
                                </JoyrideStepContent>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_PREVIEW}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        },
                        {
                            title: <JoyrideStepTitle text="Edit your workspace" />,
                            content: <JoyrideStepContent>Customize your workspace with your own name and logo.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_DASHBOARD_EDIT}`,
                            placementBeacon: 'bottom-end',
                            disableBeacon: false
                        }
                    ]}
                />
            )}
            <div className="relative flex flex-col gap-4 md:w-[320px] md:max-w-[320px]">
                <div className="absolute right-4 top-4">
                    <EditIcon
                        width={32}
                        height={32}
                        onClick={() => {
                            openBottomSheetModal('WORKSPACE_SETTINGS');
                        }}
                        className="text-black-600 hover:text-black-700 hover:bg-black-100 cursor-pointer rounded p-2"
                    />
                </div>
                <WorkspaceDetailsCard workspace={workspace} />
                <WorkspaceLinkCard />
                {workspace?.customDomain && workspace?.customDomainVerified && <WorkspaceLinkCard customDomain />}
            </div>
            {/* <div className="bg-white pt-4 pb-5 px-5 lg:px-10 shadow-overview">
                <WorkspaceDashboardOverview workspace={props.workspace} />
            </div> */}
            <div className="flex-1">
                {pinnedForms?.length > 0 && <WorkspaceDashboardPinnedForms workspacePinnedForms={pinnedFormsResponse} title={t('PINNED_FORMS')} workspace={workspace} hasCustomDomain={hasCustomDomain} />}
                <WorkspaceDashboardForms isWorkspace showButtons={pinnedForms?.length === 0} workspace={workspace} hasCustomDomain={hasCustomDomain} />
            </div>
        </DashboardLayout>
    );
}

const WorkspaceLinkCard = ({ customDomain = false }: { customDomain?: boolean }) => {
    const workspace = useAppSelector(selectWorkspace);
    return (
        <div className=" flex flex-col gap-2 rounded-lg bg-white p-4">
            <div className="p5 text-black-600 flex justify-between">
                <span className=" ">Workspace Link</span>
                <a className="hover:text-black-800 flex items-center gap-2" target="_blank" referrerPolicy="no-referrer" href={getWorkspaceShareURL(workspace, customDomain)}>
                    <OpenLinkIcon className="inline" />
                    <span>Go to link</span>
                </a>
            </div>
            <div className="bg-black-100 text-black-800 break-all rounded-lg px-3 py-2 text-xs">{getWorkspaceShareURL(workspace, customDomain)}</div>
            <div className="flex justify-between">
                <Button
                    variant={'v2Button'}
                    onClick={() => {
                        navigator.clipboard.writeText(getWorkspaceShareURL(workspace, customDomain));
                        toast('Copied');
                    }}
                >
                    Copy
                </Button>
                {(!workspace?.customDomain || !workspace.customDomainVerified) && !customDomain && (
                    <a href={`/${workspace.workspaceName}/dashboard/custom-domain`} className="text-black-600 hover:text-black-800 flex cursor-pointer items-center gap-2 text-xs">
                        Use Custom Domain <ProLogo />
                    </a>
                )}
            </div>
        </div>
    );
};

export { getAuthUserPropsWithWorkspace as getServerSideProps } from '@app/lib/serverSideProps';
