import CopyIcon from '@Components/Common/Icons/Common/Copy';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import BannerImageComponent from '@Components/dashboard/banner-image';
import { EyeIcon } from '@app/Components/icons/eye-icon';
import Globe from '@app/Components/icons/flags/globe';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import WorkspaceInfo from '@app/Components/settings/basic-information/workspace-info';
import ActiveLink from '@app/Components/ui/links/active-link';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceState, selectWorkspace } from '@app/store/workspaces/slice';
import { getWorkspaceShareURL } from '@app/utils/workspaceUtils';
import { useRouter } from 'next/navigation';

export default function WorkspaceDetails() {
    const workspace: WorkspaceState = useAppSelector(selectWorkspace);
    const router = useRouter();

    const { openModal: openFullScreenModal } = useFullScreenModal();
    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="w-full">
            <div className="shadow-settings mb-10 flex flex-col items-start gap-2 px-5 py-4 md:px-20 lg:flex-row lg:items-center">
                <div
                    className="mr-4 flex cursor-pointer items-center gap-4"
                    onClick={() => {
                        copyToClipboard(getWorkspaceShareURL(workspace));
                        toast('Copied', { type: 'info' });
                    }}
                >
                    <span className="p2-new text-black-700">{getWorkspaceShareURL(workspace)}</span>
                    <CopyIcon className="text-black-700" />
                </div>
                <div className="flex gap-2 md:gap-6">
                    {(!workspace.isPro || !workspace.customDomain || !workspace.customDomainVerified) && (
                        <AppButton
                            variant={ButtonVariant.Ghost}
                            icon={<Globe width={20} height={20} strokeWidth={1} />}
                            onClick={() => {
                                if (workspace?.isPro) {
                                    router.push(`/${workspace.workspaceName}/dashboard/custom-domain`);
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
            <div className="w-full max-w-full px-5 md:px-20">
                <BannerImageComponent workspace={workspace} isFormCreator={true} />
            </div>
            <div className="lg:px-30 px-5 md:px-20">
                <WorkspaceInfo workspace={workspace} />
            </div>
        </div>
    );
}
