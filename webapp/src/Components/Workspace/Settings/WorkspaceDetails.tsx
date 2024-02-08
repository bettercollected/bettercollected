import React from 'react';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
import Globe from '@app/components/icons/flags/globe';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceState, selectWorkspace } from '@app/store/workspaces/slice';
import { getWorkspaceShareURL } from '@app/utils/workspaceUtils';

export default function WorkspaceDetails() {
    const workspace: WorkspaceState = useAppSelector(selectWorkspace);

    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="w-full">
            <div className="flex gap-2 flex-col lg:flex-row lg:items-center items-start py-4 px-5 mb-10 md:px-20 shadow-settings">
                <div
                    className="items-center cursor-pointer flex mr-4 gap-10"
                    onClick={() => {
                        copyToClipboard(getWorkspaceShareURL(workspace));
                        toast('Copied', { type: 'info' });
                    }}
                >
                    <span className="p2-new text-black-700">{getWorkspaceShareURL(workspace)}</span>
                    <CopyIcon className="text-black-700" />
                </div>
                <div className="flex gap-2 md:gap-6">
                    {(!workspace.isPro || workspace.customDomain) && (
                        <AppButton variant={ButtonVariant.Ghost} icon={<Globe width={16} height={16} />}>
                            Use Custom Domain
                        </AppButton>
                    )}
                    <AppButton variant={ButtonVariant.Ghost} icon={<EyeIcon width={16} height={16} />}>
                        Preview as audience
                    </AppButton>
                </div>
            </div>
            <div className="w-full md:px-20 px-5 max-w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={true} />
            </div>
            <div className="px-5 md:px-20 lg:px-30">
                <WorkspaceInfo workspace={workspace} />
            </div>
        </div>
    );
}
