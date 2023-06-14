import React from 'react';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';

export default function WorkspacePreviewModal() {
    const { closeModal } = useFullScreenModal();

    return (
        <div
            className="p-5 md:p-10 md:px-20 lg:px-30 xl:px-40 min-h-screen flex flex-col justify-center min-w-screen"
            onClick={(event: any) => {
                if (event.target === event.currentTarget) closeModal();
            }}
        >
            <div>
                <div className="bg-white relative overflow-hidden pointer-events-none h-full rounded-lg ">
                    <div
                        className="absolute top-5 rounded-full bg-brand-100 p-2 right-5 cursor-pointer z-20 !pointer-events-auto"
                        onClick={() => {
                            closeModal();
                        }}
                    >
                        <Close />
                    </div>
                    <WorkspaceHomeContainer isCustomDomain={false} />
                </div>
            </div>
        </div>
    );
}
