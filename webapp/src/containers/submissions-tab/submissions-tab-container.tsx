import FormCard from '@app/components/dashboard/form-card';
import { InfoIcon } from '@app/components/icons/info-icon';
import { NormalGridIcon } from '@app/components/icons/normal-grid';
import Logo from '@app/components/ui/logo';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';

export default function SubmissionTabContainer() {
    const paramTabs = [
        {
            title: 'Forms',
            path: 'forms',
            icon: <NormalGridIcon className="h-auto w-4" />
        },
        {
            title: 'My Submissions',
            path: 'my-submissions',
            icon: <InfoIcon className="h-auto w-4" />
        }
    ];
    return (
        <div className="mt-5 flex flex-col pb-5 xl:mt-9">
            <ParamTab tabMenu={paramTabs}>
                <TabPanel className="focus:outline-none" key="forms">
                    <FormCard />
                </TabPanel>
                <TabPanel className="focus:outline-none" key="my-submissions">
                    <div>Hello submissions</div>
                </TabPanel>
            </ParamTab>
        </div>
    );
}
