import React from 'react';

import { TipList } from '@Components/FormBuilder/BuilderTips/tipsList';
import { Divider } from '@mui/material';

import { Close } from '@app/components/icons/close';

import { useModal } from '../context';

const FormBuilderTipsModalView = () => {
    const { closeModal } = useModal();
    return (
        <div className="min-h-[465px] md:w-[792px] bg-white rounded-2xl overflow-hidden">
            <div className="px-6 flex justify-between py-4">
                <h1>Tips</h1>
                <Close onClick={() => closeModal()} className="cursor-pointer" />
            </div>
            <Divider />
            <div className="p-4 md:p-6 flex flex-col">
                <h1 className="sh1">Shortcut:</h1>
                <div className="grid grid-cols-1 md:grid-cols-2 w-fit gap-6 p-2 md:p-6 md:pb-10 min-h-[350px]">
                    <TipList className="flex flex-row gap-4 xs:gap-20 md:gap-10 px-4" />
                </div>
            </div>
        </div>
    );
};

export default FormBuilderTipsModalView;
