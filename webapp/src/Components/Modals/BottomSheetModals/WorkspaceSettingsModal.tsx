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
export default function WorkspaceSettingsModal() {
    return (
        <BottomSheetModalWrapper>
            <div className="h2-new mb-2 text-black-800">Workspace Settings</div>
            <div className="p2-new text-black-700 max-w-[660px] mb-10">Crafting Your Workspace Identity: Tailor Title, Refine Description, Upload Profile Image, and Elevate with a Banner Image</div>

            {/*<ParamTab tabMenu={tabMenu} isRouteChangeable={false}>*/}
            {/*    <TabPanel key="workspace-details">*/}
            <WorkspaceDetails />
            {/*</TabPanel>*/}
            {/*<TabPanel key="other-settings">*/}
            {/*    <OtherSettings />*/}
            {/*</TabPanel>*/}
            {/*<TabPanel key="manage-url">*/}
            <ManageURLs />
            {/*    </TabPanel>*/}
            {/*</ParamTab>*/}
        </BottomSheetModalWrapper>
    );
}
