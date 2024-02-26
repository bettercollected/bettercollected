import React, { ReactNode } from 'react';

import Divider from '@mui/material/Divider';
import cn from 'classnames';

import { Close } from '@app/components/icons/close';
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
                <div className={'absolute top-3 right-5 cursor-pointer hover:bg-black-200 hover:rounded-sm p-1'}>
                    {showClose && (
                        <Close
                            onClick={() => {
                                closeModal();
                            }}
                        />
                    )}
                </div>
            </div>
            <Divider />
            <div className={cn('flex flex-col p-10 !pt-6', className)}>{children}</div>
        </div>
    );
}
