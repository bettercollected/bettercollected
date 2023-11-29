import BottomSheetModalWrapper from '@Components/Modals/BottomSheetModals/BottomSheetModalWrapper';
import ManageURLs from '@Components/Workspace/Settings/ManageURLs';
import WorkspaceDetails from '@Components/Workspace/Settings/WorkspaceDetails';

import ParamTab, { TabPanel } from '@app/components/ui/param-tab';

const tabMenu = [
    {
        title: 'Workspace Details',
        path: 'workspace-details'
    },
    // {
    //     title: 'Other Settings',
    //     path: 'other-settings'
    // },
    {
        title: 'Manage URLs',
        path: 'manage-url'
    }
];
export default function WorkspaceSettingsModal({ initialIndex }: { initialIndex?: number }) {
    return (
        <BottomSheetModalWrapper className="!px-0 pb-10">
            <div className="px-5 md:px-20 lg:px-30">
                <div className="h2-new mb-2 text-black-800">Workspace Settings</div>
                <div className="p2-new text-black-700 max-w-[660px] mb-10">Crafting Your Workspace Identity: Tailor Title, Refine Description, Upload Profile Image, and Elevate with a Banner Image</div>
            </div>
            <ParamTab initialIndex={initialIndex} tabMenu={tabMenu} isRouteChangeable={false} className="px-5 md:px-20 lg:px-30">
                <TabPanel key="workspace-details">
                    <WorkspaceDetails />
                </TabPanel>
                {/*<TabPanel key="other-settings">*/}
                {/*    <OtherSettings />*/}
                {/*</TabPanel>*/}
                <TabPanel key="manage-url">
                    <div className="px-5 md:px-20 lg:px-30">
                        <ManageURLs />
                    </div>
                </TabPanel>
            </ParamTab>
        </BottomSheetModalWrapper>
    );
}
