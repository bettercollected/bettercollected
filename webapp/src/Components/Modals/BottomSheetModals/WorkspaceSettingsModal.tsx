import { useTranslation } from 'next-i18next';

import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import ManageURLs from '@Components/Workspace/Settings/ManageURLs';
import WorkspaceDetails from '@Components/Workspace/Settings/WorkspaceDetails';

import ParamTab, { TabPanel } from '@app/components/ui/param-tab';


export default function WorkspaceSettingsModal({ initialIndex }: { initialIndex?: number }) {
    const { t } = useTranslation();

    const tabMenu = [
        {
            title: t('WORKSPACE.SETTINGS.TABS.DETAILS'),
            path: 'workspace-details'
        },
        {
            title: t('MANAGE_URLS'),
            path: 'manage-url'
        }
    ];
    return (
        <BottomSheetModalWrapper className="!px-0 pb-10">
            <div className="px-5 md:px-20 lg:px-30">
                <div className="h2-new mb-2 text-black-800">{t('WORKSPACE.SETTINGS.DEFAULT')}</div>
                <div className="p2-new text-black-700 max-w-[660px] mb-10">{t('WORKSPACE.SETTINGS.DESCRIPTION')}</div>
            </div>
            <ParamTab initialIndex={initialIndex} tabMenu={tabMenu} isRouteChangeable={false} className="px-5 md:px-20 lg:px-30">
                <TabPanel key="workspace-details">
                    <WorkspaceDetails />
                </TabPanel>

                <TabPanel key="manage-url">
                    <div className="px-5 md:px-20 lg:px-30">
                        <ManageURLs />
                    </div>
                </TabPanel>
            </ParamTab>
        </BottomSheetModalWrapper>
    );
}