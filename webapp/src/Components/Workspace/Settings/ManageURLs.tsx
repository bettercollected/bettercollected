import React from 'react';

import { useTranslation } from 'next-i18next';

import CopyIcon from '@Components/Common/Icons/Common/Copy';
import DeleteIcon from '@Components/Common/Icons/Common/Delete';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import Pro from '@Components/Common/Icons/Dashboard/Pro';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import Globe from '@app/components/icons/flags/globe';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageURLs() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const { openModal: openFullScreenModal } = useFullScreenModal();

    const isAdmin = useAppSelector(selectIsAdmin);

    const isProWorkspace = useAppSelector(selectIsProPlan);

    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className="mt-6 max-w-[788px]">
            <div>
                <div className="h3-new mb-2">{t('WORKSPACE.SETTINGS.URLS.TITLE')}</div>
                <div className="flex flex-col md:flex-row gap-6">
                    <span className="p2-new text-black-700">{t('WORKSPACE.SETTINGS.URLS.DESCRIPTION')}</span>
                    <AppButton
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
                <div className="p2-new flex gap-4 items-center">
                    <span>
                        {environments.HTTP_SCHEME}
                        {environments.CLIENT_DOMAIN}/<span className="text-pink">{workspace.workspaceName}</span>
                    </span>
                    <div>
                        <AppButton
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
                <div className="h4-new flex items-center gap-2">
                    {t('CUSTOM_DOMAIN')}

                    <div className="flex items-center rounded gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                        <Pro width={12} height={12} />
                        <span className="leading-none">Pro</span>
                    </div>
                </div>
                {isAdmin && !workspace?.customDomain && (
                    <div className="border-y border-y-black-200 py-4 flex flex-col gap-4 mt-4">
                        <span className="p2-new text-black-700">Add a domain purchased through a web hosting service.</span>
                        <div>
                            <AppButton
                                variant={ButtonVariant.Secondary}
                                icon={<Globe />}
                                onClick={() => {
                                    if (isProWorkspace) {
                                        openModal('UPDATE_WORKSPACE_DOMAIN');
                                    } else {
                                        openFullScreenModal('UPGRADE_TO_PRO');
                                    }
                                }}
                            >
                                Add Custom Domain
                            </AppButton>
                        </div>
                    </div>
                )}

                {workspace?.customDomain && (
                    <div className="flex justify-between items-center gap-4 p2-new border-y border-y-black-200 py-4 mt-4">
                        <div className="flex items-center gap-4">
                            <div>
                                {environments.HTTP_SCHEME}
                                <span className="text-pink">{workspace?.customDomain}</span>
                            </div>
                            <AppButton
                                size={ButtonSize.Tiny}
                                variant={ButtonVariant.Ghost}
                                icon={<CopyIcon width={16} height={16} />}
                                onClick={() => {
                                    copyToClipboard(`${environments.HTTP_SCHEME}${workspace?.customDomain}`);
                                    toast('Copied', { type: 'info' });
                                }}
                            >
                                {t('BUTTON.COPY')}
                            </AppButton>
                        </div>
                        <AppButton
                            onClick={() => {
                                openModal('DELETE_CUSTOM_DOMAIN');
                            }}
                            size={ButtonSize.Tiny}
                            variant={ButtonVariant.DangerGhost}
                            icon={<DeleteIcon width={16} height={16} />}
                        >
                            {t('BUTTON.REMOVE')}
                        </AppButton>
                    </div>
                )}
            </div>
        </div>
    );
}
