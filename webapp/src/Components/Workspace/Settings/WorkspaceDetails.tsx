import React from 'react';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { toast } from 'react-toastify';

import BannerImageComponent from '@app/components/dashboard/banner-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
import Globe from '@app/components/icons/flags/globe';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import WorkspaceInfo from '@app/components/settings/basic-information/workspace-info';
import ActiveLink from '@app/components/ui/links/active-link';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceState, selectWorkspace } from '@app/store/workspaces/slice';
import { getWorkspaceShareURL } from '@app/utils/workspaceUtils';

export default function WorkspaceDetails() {
    const workspace: WorkspaceState = useAppSelector(selectWorkspace);

    const { openModal } = useModal();

    const { closeBottomSheetModal } = useBottomSheetModal();

    const { openModal: openFullScreenModal } = useFullScreenModal();
    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="w-full">
            <div className="flex gap-2 flex-col lg:flex-row lg:items-center items-start py-4 px-5 mb-10 md:px-20 shadow-settings">
                <div
                    className="items-center cursor-pointer flex mr-4 gap-4"
                    onClick={() => {
                        copyToClipboard(getWorkspaceShareURL(workspace));
                        toast('Copied', { type: 'info' });
                    }}
                >
                    <span className="p2-new text-black-700">{getWorkspaceShareURL(workspace)}</span>
                    <CopyIcon className="text-black-700" />
                </div>
                <div className="flex gap-2 md:gap-6">
                    {(!workspace.isPro || !workspace.customDomain) && (
                        <AppButton
                            variant={ButtonVariant.Ghost}
                            icon={<Globe width={20} height={20} strokeWidth={1} />}
                            onClick={() => {
                                if (workspace?.isPro) {
                                    openModal('UPDATE_WORKSPACE_DOMAIN');
                                } else {
                                    openFullScreenModal('UPGRADE_TO_PRO');
                                }
                            }}
                        >
                            Use Custom Domain
                        </AppButton>
                    )}
                    <ActiveLink href={getWorkspaceShareURL(workspace)} target="_blank" referrerPolicy="no-referrer">
                        <AppButton variant={ButtonVariant.Ghost} icon={<EyeIcon width={20} height={20} />}>
                            Preview as audience
                        </AppButton>
                    </ActiveLink>
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
