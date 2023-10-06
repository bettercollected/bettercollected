import React from 'react';

import cn from 'classnames';

import SelectGroup from '@app/components/group/select-group';
import { Close } from '@app/components/icons/close';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

const SelectGroupFullModalView = () => {
    const { closeModal } = useFullScreenModal();
    return (
        <div className={cn('flex w-full min-h-screen !bg-transparent pt-40 overflow-hidden')}>
            <div className="bg-white w-16 h-16 fixed top-20 z-[3000] right-10 shadow-lg rounded-full flex items-center justify-center cursor-pointer" onClick={closeModal}>
                <Close width="32px" height="40px" stroke="#4D4D4D" strokeWidth={0.8} />
            </div>
            <div className={cn(' w-full bg-white min-h-screen rounded-t-3xl !mt-0 !pt-12 overflow-y-auto scroll-mt-6')}>
                <div className="pt-12 px-2 md:px-[120px] justify-between flex flex-row w-full">
                    <SelectGroup />
                </div>
            </div>
        </div>
    );
};
export default SelectGroupFullModalView;
