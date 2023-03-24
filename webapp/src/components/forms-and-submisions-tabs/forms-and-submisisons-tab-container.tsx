import { Feed } from '@mui/icons-material';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';

import { HistoryIcon } from '../icons/history';
import { TrashIcon } from '../icons/trash';

interface ISubmissionTabContainer {
    workspaceId: string;
    showResponseBar: boolean;
    workspace: any;
}

export default function FormsAndSubmissionsTabContainer({ showResponseBar, workspace }: ISubmissionTabContainer) {
    const paramTabs = [
        {
            icon: <Feed />,
            title: 'Forms',
            path: 'forms'
        }
    ];

    if (!showResponseBar && paramTabs.length === 1) {
        paramTabs.push({
            icon: <HistoryIcon className="w-[20px] h-[20px]" />,
            title: 'My Submissions',
            path: 'mySubmissions'
        });
        paramTabs.push({
            icon: <TrashIcon className="w-[20px] h-[20px]" />,
            title: 'Deletion Requests',
            path: 'deletion-requests'
        });
    } else if (showResponseBar && paramTabs.length === 3) {
        paramTabs.pop();
        paramTabs.pop();
    }

    return (
        <ParamTab tabMenu={paramTabs}>
            <TabPanel className="focus:outline-none" key="forms">
                <WorkspaceFormsTabContent workspace={workspace} />
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
