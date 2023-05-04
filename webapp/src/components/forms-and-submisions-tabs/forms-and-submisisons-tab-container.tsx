import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import { FormIcon } from '@app/components/icons/form-icon';
import { HistoryIcon } from '@app/components/icons/history';
import { TrashIcon } from '@app/components/icons/trash';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';

interface ISubmissionTabContainer {
    workspaceId: string;
    showResponseBar: boolean;
    workspace: any;
    isFormCreator?: boolean;
}

export default function FormsAndSubmissionsTabContainer({ showResponseBar, workspace, isFormCreator = false }: ISubmissionTabContainer) {
    const paramTabs = [
        {
            icon: <FormIcon />,
            title: 'Public forms',
            path: 'forms'
        }
    ];

    if (!showResponseBar && paramTabs.length === 1) {
        paramTabs.push({
            icon: <HistoryIcon className="w-5 h-5" />,
            title: 'Submitted forms',
            path: 'mySubmissions'
        });
        paramTabs.push({
            icon: <TrashIcon className="w-5 h-5" />,
            title: 'Deletion requests',
            path: 'deletion-requests'
        });
    } else if (showResponseBar && paramTabs.length === 3) {
        paramTabs.pop();
        paramTabs.pop();
    }

    return (
        <ParamTab className="pb-[28px] bg-brand-100 !mb-0 px-5 lg:px-10 xl:px-20" tabMenu={paramTabs}>
            <TabPanel className="focus:outline-none" key="forms">
                <WorkspaceFormsTabContent isFormCreator={isFormCreator} workspace={workspace} />
            </TabPanel>
            <TabPanel className="focus:outline-none" key="mySubmissions">
                <WorkspaceResponsesTabContent workspace={workspace} />
            </TabPanel>
            <TabPanel className="focus:outline-none" key="deletion-requests">
                <WorkspaceResponsesTabContent workspace={workspace} deletionRequests />
            </TabPanel>
        </ParamTab>
    );
}
