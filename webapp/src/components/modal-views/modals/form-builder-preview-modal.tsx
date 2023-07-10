import React from 'react';

import { Close } from '@app/components/icons/close';

import { useFullScreenModal } from '../full-screen-modal-context';

export default function FormBuilderPreviewModal() {
    const { closeModal } = useFullScreenModal();

    return (
        <div className="relative h-full w-full overflow-auto pt-10 !bg-white ">
            <Close
                className="absolute cursor-pointer text-black-600 top-10 right-10"
                height={20}
                width={20}
                onClick={() => {
                    closeModal();
                }}
            />
            <div className="container p-10  w-full h-full mx-auto flex flex-col items-center justify-center">Form Builder Components</div>
        </div>
    );
}
