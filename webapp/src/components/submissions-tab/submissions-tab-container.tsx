import FormCard from '@app/components/dashboard/form-card';
import ResponseCard from '@app/components/dashboard/response-card';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';

interface ISubmissionTabContainer {
    workspaceId: string;
    showResponseBar: boolean;
    workspace: any;
}

export default function SubmissionTabContainer({ workspaceId, showResponseBar, workspace }: ISubmissionTabContainer) {
    const paramTabs = [
        {
            title: 'Forms',
            path: 'forms'
        }
    ];

    if (!showResponseBar && paramTabs.length === 1) {
        paramTabs.push({
            title: 'My Submissions',
            path: 'mySubmissions'
        });
    } else if (!!showResponseBar && paramTabs.length === 2) {
        paramTabs.pop();
    }

    return (
        <ParamTab tabMenu={paramTabs}>
            <TabPanel className="focus:outline-none" key="forms">
                <FormCard workspace={workspace} />
            </TabPanel>
            <TabPanel className="focus:outline-none" key="mySubmissions">
                <ResponseCard workspace={workspace} />
            </TabPanel>
        </ParamTab>
    );
}
