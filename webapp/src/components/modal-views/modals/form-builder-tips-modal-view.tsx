import React from 'react';

import { TipList } from '@Components/FormBuilder/BuilderTips/tipsList';
import { Divider } from '@mui/material';

import { Close } from '@app/components/icons/close';

import { useModal } from '../context';

const FormBuilderTipsModalView = () => {
    const { closeModal } = useModal();
    return (
        <div className="h-[465px] md:w-[792px] bg-white rounded-2xl overflow-hidden">
            <div className="px-6 flex justify-between py-4">
                <h1>Tips</h1>
                <Close onClick={() => closeModal()} />
            </div>
            <Divider />
            <div className="p-4 md:p-6 flex flex-col">
                <h1 className="sh1">Shortcut:</h1>
                <div className="flex flex-col flex-wrap gap-1 w-fit md:gap-6 p-2 md:p-6 md:pb-10 h-[350px]">
                    <TipList className="flex flex-row gap-4 xs:gap-20 md:gap-10 px-4" />
                </div>
            </div>
        </div>
    );
};

export default FormBuilderTipsModalView;
