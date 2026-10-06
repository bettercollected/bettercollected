import { ReactNode } from 'react';

import Divider from '@Components/common/divider';
import { cn } from '@app/shadcn/util/lib';

import ModalCloseButton from '@app/components/modal-views/modal-close-button';
import { useModal } from '@app/components/modal-views/context';

interface HeaderModalWrapperProps {
    headerTitle?: string;
    children?: ReactNode;
    showClose?: boolean;
    className?: string;
}

export default function HeaderModalWrapper({ headerTitle = '', children, showClose = true, className }: HeaderModalWrapperProps) {
    const { closeModal } = useModal();

    return (
        <div className="flex flex-col bg-white rounded-md w-full min-w-[350px] lg:min-w-[386px] max-w-[556px]">
            <div className="p-4 flex items-center justify-between">
                <span className="text-black-800 text-sm p2-new">{headerTitle}</span>
                {showClose && <ModalCloseButton onClick={closeModal} className="absolute right-5 top-3 h-8 w-8" iconClassName="h-6 w-6" />}
            </div>
            <Divider />
            <div className={cn('flex flex-col p-10 !pt-6', className)}>{children}</div>
        </div>
    );
}
