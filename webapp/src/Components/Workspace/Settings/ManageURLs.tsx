import React from 'react';

import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import EditIcon from '@Components/Common/Icons/Edit';
import Pro from '@Components/Common/Icons/Pro';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { toast } from 'react-toastify';

import Globe from '@app/components/icons/flags/globe';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ManageURLs() {
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();

    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className="mt-6 max-w-[788px]">
            <div>
                <div className="h3-new mb-2">Workspace URL</div>
                <div className="flex flex-col md:flex-row gap-6">
                    <span className="p2-new text-black-700">Customize your workspace handle name to make your workspace more personal. A link slug is a brief, descriptive part of a URL that identifies web page content.</span>
                    <AppButton
                        icon={<EditIcon />}
                        variant={ButtonVariant.Ghost}
                        onClick={() => {
                            openModal('UPDATE_WORKSPACE_HANDLE');
                        }}
                    >
                        Change Slug
                    </AppButton>
                </div>
            </div>
            <div className="mt-[72px]">
                <div className="h4-new mb-2">Default URL</div>
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
                            Copy
                        </AppButton>
                    </div>
                </div>
            </div>
            <div className="mt-12">
                <div className="h4-new flex items-center gap-2">
                    Custom Domain{' '}
                    <div className="flex items-center rounded gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                        <Pro width={12} height={12} />
                        <span className="leading-none">Pro</span>
                    </div>
                </div>
                {!workspace?.customDomain && (
                    <div className="border-y border-y-black-200 py-4 flex flex-col gap-4 mt-4">
                        <span className="p2-new text-black-700">Add a domain purchased through a web hosting service.</span>
                        <div>
                            <AppButton
                                variant={ButtonVariant.Secondary}
                                icon={<Globe />}
                                onClick={() => {
                                    openModal('UPDATE_WORKSPACE_DOMAIN');
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
                                    copyToClipboard(`${environments.HTTP_SCHEME}${environments.CLIENT_DOMAIN}/${workspace.workspaceName}`);
                                    toast('Copied', { type: 'info' });
                                }}
                            >
                                Copy
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
                            Remove
                        </AppButton>
                    </div>
                )}
            </div>
        </div>
    );
}
