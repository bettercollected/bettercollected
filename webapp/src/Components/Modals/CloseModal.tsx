import React from 'react';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';

export default function CloseModal() {
    const { closeModal } = useModal();

    return (
        <div className="absolute p-1 hover:bg-black-200 top-5 right-5">
            <Close
                onClick={() => {
                    closeModal();
                }}
            />
        </div>
    );
}
