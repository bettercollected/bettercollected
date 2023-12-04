import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import PlusIcon from '@Components/Common/Icons/Common/Plus';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceState, selectWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceDetails() {
    const { t } = useTranslation();
    const workspace: WorkspaceState = useAppSelector(selectWorkspace);
    const [showBannerImageComponent, setShowBannerImageComponent] = useState(!!workspace.bannerImage);

    return (
        <div>
            {!showBannerImageComponent && (
                <div className="px-5 md:px-20 lg:px-30">
                    <AppButton
                        variant={ButtonVariant.Ghost}
                        icon={<PlusIcon />}
                        onClick={() => {
                            setShowBannerImageComponent(true);
                        }}
                    >
                        {t('WORKSPACE.SETTINGS.DETAILS.ADD_COVER_IMAGE')}
                    </AppButton>
                </div>
            )}

            {showBannerImageComponent && (
                <div className="w-full">
                    <BannerImageComponent workspace={workspace} isFormCreator={true} />
                </div>
            )}
            <div className="px-5 md:px-20 lg:px-30">
                <WorkspaceInfo workspace={workspace} />
            </div>
        </div>
    );
}
