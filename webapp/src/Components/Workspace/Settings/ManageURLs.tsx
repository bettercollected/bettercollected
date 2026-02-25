import { useTranslation } from 'next-i18next';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import EditIcon from '@Components/Common/Icons/Common/Edit';

import { CustomDomainCard } from '@app/app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard/custom-domain/page';
import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth, selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageURLs() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const { toast } = useToast();
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const auth = useAppSelector(selectAuth);

    const isAdmin = useAppSelector(selectIsAdmin);

    const isProWorkspace = useAppSelector(selectIsProPlan);

    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className="mt-10 max-w-[788px]">
            <div>
                <div className="h3-new mb-2">{t('WORKSPACE.SETTINGS.URLS.TITLE')}</div>
                <div className="flex flex-col gap-6 md:flex-row">
                    <span className="p2-new text-black-700">{t('WORKSPACE.SETTINGS.URLS.DESCRIPTION')}</span>
                    <Button
                        data-umami-event="Customize Workspace Link"
                        data-umami-event-email={auth.email}
                        variant="ghost"
                        onClick={() => {
                            openModal('UPDATE_WORKSPACE_HANDLE');
                        }}
                    >
                        <EditIcon className="mr-2" />
                        {t('FORM_PAGE.SETTINGS.LINKS.CHANGE_SLUG')}
                    </Button>
                </div>
            </div>
            <div className="mt-[72px]">
                <div className="h4-new mb-2">{t('WORKSPACE.SETTINGS.URLS.DEFAULT')}</div>
                <div className="p2-new flex items-center gap-4">
                    <span>
                        {environments.HTTP_SCHEME}
                        {environments.FORM_DOMAIN}/<span className="text-pink">{workspace.workspaceName}</span>
                    </span>
                    <div>
                        <Button
                            data-umami-event="Copy Default Workspace Link From Workspace Setting"
                            data-umami-event-email={auth.email}
                            size="icon"
                            variant="ghost"
                            onClick={() => {
                                copyToClipboard(`${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}/${workspace.workspaceName}`);
                                toast({ description: 'Copied' });
                            }}
                        >
                            <CopyIcon width={16} height={16} />{/* check if I need children here, original was Copy */}
                            {t('BUTTON.COPY')}
                        </Button>
                    </div>
                </div>
            </div>
            <div className="mt-12">
                <CustomDomainCard />
            </div>
        </div>
    );
}
