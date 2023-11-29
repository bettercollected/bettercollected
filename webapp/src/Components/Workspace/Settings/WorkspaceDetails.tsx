import React, { useState } from 'react';

import PlusIcon from '@Components/Common/Icons/Plus';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceState, selectWorkspace } from '@app/store/workspaces/slice';

export default function WorkspaceDetails() {
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
                        Add Cover Image
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
