import React, { ReactNode } from 'react';

import cn from 'classnames';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

export default function BottomSheetModalWrapper({ children, className }: { children?: ReactNode; className?: string }) {
    const { closeModal } = useFullScreenModal();
    return (
        <div className={cn('flex w-full min-h-screen !bg-transparent pt-40 overflow-hidden')}>
            <div className="bg-white w-16 h-16 fixed top-20 z-[3000] right-10 shadow-lg rounded-full flex items-center justify-center cursor-pointer" onClick={closeModal}>
                <Close width="32px" height="40px" stroke="#4D4D4D" strokeWidth={0.8} />
            </div>
            <div className={cn(' w-full  bg-white min-h-screen rounded-t-3xl px-5 md:px-20 lg:px-30 !mt-0 !pt-12 overflow-y-auto scroll-mt-6', className)}>{children}</div>
        </div>
    );
}
