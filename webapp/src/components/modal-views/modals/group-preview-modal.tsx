import React from 'react';

import { Close } from '@mui/icons-material';

import { useModal } from '@app/components/modal-views/context';

export default function GroupPreview() {
    const { closeModal } = useModal();
    return (
        <div className="p-7 bg-white relative rounded-[8px] md:max-w-[670px]">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
        </div>
    );
}
