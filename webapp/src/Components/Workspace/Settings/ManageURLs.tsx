import { useTranslation } from 'next-i18next';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import DeleteIcon from '@Components/Common/Icons/Common/Delete';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import Globe from '@app/Components/icons/flags/globe';
import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import { ProLogo } from '@app/Components/ui/logo';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { selectAuth, selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useRouter } from 'next/router';
import { CustomDomainCard } from '@app/pages/[workspace_name]/dashboard/custom-domain';

export default function ManageURLs() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();
    const auth = useAppSelector(selectAuth);

    const router = useRouter();
    const isAdmin = useAppSelector(selectIsAdmin);

    const isProWorkspace = useAppSelector(selectIsProPlan);

    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className="mt-10 max-w-[788px]">
            <div>
                <div className="h3-new mb-2">{t('WORKSPACE.SETTINGS.URLS.TITLE')}</div>
                <div className="flex flex-col gap-6 md:flex-row">
                    <span className="p2-new text-black-700">{t('WORKSPACE.SETTINGS.URLS.DESCRIPTION')}</span>
                    <AppButton
                        data-umami-event="Customize Workspace Link"
                        data-umami-event-email={auth.email}
                        icon={<EditIcon />}
                        variant={ButtonVariant.Ghost}
                        onClick={() => {
                            openModal('UPDATE_WORKSPACE_HANDLE');
                        }}
                    >
                        {t('FORM_PAGE.SETTINGS.LINKS.CHANGE_SLUG')}
                    </AppButton>
                </div>
            </div>
            <div className="mt-[72px]">
                <div className="h4-new mb-2">{t('WORKSPACE.SETTINGS.URLS.DEFAULT')}</div>
                <div className="p2-new flex items-center gap-4">
                    <span>
                        {environments.HTTP_SCHEME}
                        {environments.CLIENT_DOMAIN}/<span className="text-pink">{workspace.workspaceName}</span>
                    </span>
                    <div>
                        <AppButton
                            data-umami-event="Copy Default Workspace Link From Workspace Setting"
                            data-umami-event-email={auth.email}
                            size={ButtonSize.Tiny}
                            variant={ButtonVariant.Ghost}
                            icon={<CopyIcon width={16} height={16} />}
                            onClick={() => {
                                copyToClipboard(`${environments.HTTP_SCHEME}${environments.CLIENT_DOMAIN}/${workspace.workspaceName}`);
                                toast('Copied', { type: 'info' });
                            }}
                        >
                            {t('BUTTON.COPY')}
                        </AppButton>
                    </div>
                </div>
            </div>
            <div className="mt-12">
                <CustomDomainCard />
            </div>
        </div>
    );
}
