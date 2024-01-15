import React, { ReactNode } from 'react';

import Divider from '@mui/material/Divider';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';

interface HeaderModalWrapperProps {
    headerTitle?: string;
    children?: ReactNode;
}

export default function HeaderModalWrapper({ headerTitle = '', children }: HeaderModalWrapperProps) {
    const { closeModal } = useModal();

    return (
        <div className="flex flex-col bg-white rounded-md w-full min-w-[350px] max-w-[500px]">
            <div className="p-4 flex items-center justify-between">
                <span className="text-black-800 text-sm p2-new">{headerTitle}</span>
                <div className={'absolute top-3 right-5 cursor-pointer hover:bg-black-200 hover:rounded-sm p-1'}>
                    <Close
                        onClick={() => {
                            closeModal();
                        }}
                    />
                </div>
            </div>
            <Divider />
            <div className="flex flex-col p-10 !pt-6">{children}</div>
        </div>
    );
}
