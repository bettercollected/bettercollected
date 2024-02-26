import React, { ReactNode } from 'react';

import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import cn from 'classnames';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

export default function BottomSheetModalWrapper({ children, className }: { children?: ReactNode; className?: string }) {
    const { closeModal } = useFullScreenModal();
    const { closeBottomSheetModal } = useBottomSheetModal();

    const closeModals = () => {
        closeModal();
        closeBottomSheetModal();
    };
    return (
        <div
            className={cn('flex w-full min-h-screen bg-transparent pt-40 overflow-hidden cursor-pointer')}
            onClick={(event) => {
                if (event.currentTarget == event.target) {
                    closeModals();
                }
            }}
        >
            <div className="!bg-white w-16 h-16 fixed top-20 z-[3000] opacity-100 right-10 shadow-lg rounded-full flex items-center justify-center cursor-pointer" onClick={closeModals}>
                <Close width="32px" height="40px" stroke="#4D4D4D" strokeWidth={0.8} />
            </div>
            <div className={cn(' w-full !bg-white cursor-auto h-bottom-sheet-container overflow-auto rounded-t-3xl !opacity-100 px-5 md:px-20 lg:px-30 !mt-0 !pt-12 overflow-y-auto scroll-mt-6', className)}>{children}</div>
        </div>
    );
}
