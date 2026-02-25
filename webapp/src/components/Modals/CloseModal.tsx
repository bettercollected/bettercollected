import React from 'react';

import { Close } from '@app/Components/icons/close';
import { useModal } from '@app/Components/modal-views/context';


export default function CloseModal() {
    const { closeModal } = useModal();

    return (
        <div className="absolute hover:bg-black-200 top-5 right-5">
            <Close
                onClick={() => {
                    closeModal();
                }}
            />
        </div>
    );
}