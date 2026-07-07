import BannerImageComponent from '@app/components/dashboard/banner-image';
import { EyeIcon } from '@app/components/icons/eye-icon';
import Globe from '@app/components/icons/flags/globe';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import ActiveLink from '@app/components/ui/links/active-link';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { WorkspaceState, selectWorkspace } from '@app/store/workspaces/slice';
import { getWorkspaceShareURL } from '@app/utils/workspace-utils';
import WorkspaceInfo from '@Components/settings/workspace-info';
import { Copy } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function WorkspaceDetails({ showUrlRow = true }: { showUrlRow?: boolean }) {
    const workspace: WorkspaceState = useAppSelector(selectWorkspace);
    const router = useRouter();
    const { toast } = useToast();

    const { openModal: openFullScreenModal } = useFullScreenModal();
    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="w-full">
            {/* Hidden inside the Public Workspace frame — the frame's address
                bar already carries the URL, copy and open-live actions. */}
            <div className={showUrlRow ? 'shadow-settings mb-10 flex flex-col items-start gap-2 px-5 py-4 lg:flex-row lg:items-center' : 'hidden'}>
                <div
                    className="mr-4 flex cursor-pointer items-center gap-4"
                    onClick={() => {
                        copyToClipboard(getWorkspaceShareURL(workspace));
                        toast({ description: 'Copied' });
                    }}
                >
                    <span className="p2-new text-black-700">{getWorkspaceShareURL(workspace)}</span>
                    <Copy className="text-black-700" />
                </div>
                <div className="flex gap-2 md:gap-6">
                    {(!workspace.isPro || !workspace.customDomain || !workspace.customDomainVerified) && (
                        <Button
                            variant="ghost"
                            onClick={() => {
                                if (workspace?.isPro) {
                                    router.push(`/${workspace.workspaceName}/dashboard/custom-domain`);
                                } else {
                                    openFullScreenModal('UPGRADE_TO_PRO');
                                }
                            }}
                        >
                            <Globe width={20} height={20} strokeWidth={1} className="mr-2" />
                            Use Custom Domain
                        </Button>
                    )}
                    <ActiveLink href={getWorkspaceShareURL(workspace)} target="_blank" referrerPolicy="no-referrer">
                        <Button variant="ghost">
                            <EyeIcon width={20} height={20} className="mr-2" />
                            Preview as audience
                        </Button>
                    </ActiveLink>
                </div>
            </div>
            {/* No extra horizontal padding — the settings container owns the
                left edge, so the banner and form line up with the tabs. */}
            <div className="w-full max-w-[720px]">
                <BannerImageComponent workspace={workspace} isFormCreator={true} />
            </div>
            <WorkspaceInfo workspace={workspace} />
        </div>
    );
}
