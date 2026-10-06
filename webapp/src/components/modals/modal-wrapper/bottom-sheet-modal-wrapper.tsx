import { ReactNode } from 'react';

import cn from 'classnames';

import ModalCloseButton from '@app/components/modal-views/modal-close-button';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { useBottomSheetModal } from '../contexts/bottom-sheet-modal-context';

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
            <ModalCloseButton onClick={closeModals} className="!bg-white fixed right-10 top-20 z-[3000] h-16 w-16 rounded-full opacity-100 shadow-lg" iconClassName="h-8 w-8" />
            <div className={cn(' w-full !bg-white cursor-auto h-bottom-sheet-container overflow-auto rounded-t-3xl !opacity-100 px-5 md:px-20 lg:px-30 !mt-0 !pt-12 overflow-y-auto scroll-mt-6', className)}>{children}</div>
        </div>
    );
}
