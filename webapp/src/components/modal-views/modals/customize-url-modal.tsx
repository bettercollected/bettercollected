import React from 'react';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import CustomizeUrlView from '@app/components/ui/customizeUrlView';

export interface ICustomizeUrlModalProps {
    description: string;
    domain: string;
}
export default function CustomizeUrlModal({ description, domain }: ICustomizeUrlModalProps) {
    console.log(description);
    const { closeModal } = useModal();
    return (
        <div className="rounded-[4px] relative bg-white md:p-10 p-5  dark:border-gray-700 dark:bg-light-dark">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <CustomizeUrlView description={description} domain={domain} />
        </div>
    );
}
