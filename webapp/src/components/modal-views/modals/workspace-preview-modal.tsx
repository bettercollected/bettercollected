import React from 'react';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import WorkspaceHomeContainer from '@app/containers/dashboard/WorkspaceHomeContainer';

export default function WorkspacePreviewModal() {
    const { closeModal } = useFullScreenModal();

    return (
        <div
            className="p-5 md:px-20 min-h-screen min-w-screen"
            onClick={(event: any) => {
                if (event.target === event.currentTarget) {
                    closeModal();
                }
            }}
        >
            <div className="bg-white relative overflow-hidden pointer-events-none h-full rounded-lg scale-90">
                <div
                    className="absolute top-5 right-5 cursor-pointer z-20 !pointer-events-auto"
                    onClick={() => {
                        closeModal();
                    }}
                >
                    <Close />
                </div>
                <WorkspaceHomeContainer isCustomDomain={false} />
            </div>
        </div>
    );
}
