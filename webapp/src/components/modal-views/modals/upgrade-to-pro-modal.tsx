import React from 'react';

import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import UpgradeToProContainer from '@app/containers/upgrade-to-pro';

export default function UpgradeToProModal() {
    const { closeModal } = useFullScreenModal();

    return (
        <div className="h-full overflow-auto !bg-white pt-16 ">
            <Close
                className="text-black-600 absolute right-5 top-5 cursor-pointer lg:right-10 lg:top-10"
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
