import React from 'react';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import UpgradeToProContainer from '@app/containers/upgrade-to-pro';


export default function UpgradeToProModal() {
    const { closeModal } = useFullScreenModal();

    return (
        <div className="relative h-full overflow-auto !bg-white pt-20 ">
            <Close
                className="absolute cursor-pointer text-black-600 top-10 right-10"
                height={40}
                width={40}
                onClick={() => {
                    closeModal();
                }}
            />
            <UpgradeToProContainer />
        </div>
    );
}