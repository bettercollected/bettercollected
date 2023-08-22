import React from 'react';

import Link from 'next/link';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import environments from '@app/configs/environments';
import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function WorkspacePreviewModal() {
    const { closeModal } = useFullScreenModal();
    const workspace = useAppSelector(selectWorkspace);

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_DOMAIN.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_DOMAIN;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    return (
        <div
            className="p-5 md:p-10 md:px-20 flex-1 w-full lg:px-30 xl:px-40 min-h-screen flex flex-col justify-center min-w-screen"
            onClick={(event: any) => {
                if (event.target === event.currentTarget) closeModal();
            }}
        >
            <div>
                <div className="bg-white relative overflow-hidden pointer-events-none h-full rounded-lg ">
                    <div
                        className="absolute top-5 rounded-full  p-2 right-5 cursor-pointer z-20 !pointer-events-auto"
                        onClick={() => {
                            closeModal();
                        }}
                    >
                        <Close />
                    </div>
                    <div className="bg-white z-[5000] body-4 px-10 !pointer-events-auto h-fit py-6 text-center  w-full">
                        <span>This is just a preview of your workspace. To visit the real workspace</span>
                        <a href={getWorkspaceUrl()} rel="noopener noreferrer" referrerPolicy="no-referrer" target="_blank">
                            <span className="!text-brand-500 ml-1 inline-block cursor-pointer hover:underline">{' click here.'}</span>
                        </a>
                    </div>
                    <WorkspaceHomeContainer isCustomDomain={false} isWorkspacePreview={true} />
                </div>
            </div>
        </div>
    );
}
