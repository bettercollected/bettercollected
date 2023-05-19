import React from 'react';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import CustomizeUrlView from '@app/components/ui/customizeUrlView';

export interface ICustomizeUrlModalProps {
    description: string;
    url: string;
}
export default function CustomizeUrlModal({ description, url }: ICustomizeUrlModalProps) {
    const { closeModal } = useModal();
    return (
        <div className="rounded-[4px] md:p-10 p-5 relative bg-white md:w-[454px] w-full   dark:border-gray-700 dark:bg-light-dark">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <CustomizeUrlView description={description} url={url} />
        </div>
    );
}
