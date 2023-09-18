import React from 'react';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { useModal } from '@app/components/modal-views/context';

export default function ConsentModalTopBar() {
    const { closeModal } = useModal();
    return (
        <div className="flex justify-between py-4 px-6 border-b border-black-200">
            <div className="p2 !text-black-800">For how long data will be stored</div>
            <DropdownCloseIcon className="cursor-pointer" onClick={closeModal} />
        </div>
    );
}
