import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Common/Copy';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
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
            <div className="flex gap-2 flex-col lg:flex-row lg:items-center items-start mb-4 px-5 md:px-20">
                <div className="p4-new text-black-700">Workspace Link</div>
                <div
                    className="p-3 rounded bg-black-200 items-center cursor-pointer flex mr-4 gap-10"
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
                        <AppButton variant={ButtonVariant.Ghost} icon={<EditIcon width={12} height={12} />}>
                            Use Custom Domain
                        </AppButton>
                    )}
                    <AppButton variant={ButtonVariant.Ghost} icon={<EyeIcon width={16} height={12} />}>
                        Preview as audience
                    </AppButton>
                </div>
            </div>
            <Divider className="md:mx-20 mb-10" />
            <div className="w-full md:px-20 px-5 max-w-full">
                <BannerImageComponent workspace={workspace} isFormCreator={true} />
            </div>
            <div className="px-5 md:px-20 lg:px-30">
                <WorkspaceInfo workspace={workspace} />
            </div>
        </div>
    );
}
