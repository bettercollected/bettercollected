import FormCard from '@app/components/dashboard/form-card';
import ResponseCard from '@app/components/dashboard/response-card';
import { InfoIcon } from '@app/components/icons/info-icon';
import { NormalGridIcon } from '@app/components/icons/normal-grid';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';

interface ISubmissionTabContainer {
    workspaceId: string;
    showResponseBar: boolean;
}

export default function SubmissionTabContainer({ workspaceId, showResponseBar }: ISubmissionTabContainer) {
    const paramTabs = [
        {
            title: 'Forms',
            path: 'forms',
            icon: <NormalGridIcon className="h-auto w-4" />
        }
    ];

    if (!showResponseBar && paramTabs.length === 1) {
        paramTabs.push({
            title: 'My Submissions',
            path: 'mySubmissions',
            icon: <InfoIcon className="h-auto w-4" />
        });
    } else if (!!showResponseBar && paramTabs.length === 2) {
        paramTabs.pop();
    }

    return (
        <div className="mt-5 sm:mt-0 flex flex-col pb-5 xl:mt-9">
            <ParamTab tabMenu={paramTabs} isRouteChangeable={false}>
                <TabPanel className="focus:outline-none" key="forms">
                    <FormCard workspaceId={workspaceId} />
                </TabPanel>
                <TabPanel className="focus:outline-none" key="mySubmissions">
                    <ResponseCard workspaceId={workspaceId} />
                </TabPanel>
            </ParamTab>
        </div>
    );
}
