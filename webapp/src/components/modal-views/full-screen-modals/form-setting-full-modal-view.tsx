import React from 'react';

import cn from 'classnames';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { Close } from '@app/components/icons/close';

import { useFullScreenModal } from '../full-screen-modal-context';

interface IFormSettingFullModalProps {
    isSettingModal: boolean;
}

const FormSettingFullModalView = ({ isSettingModal = false }: IFormSettingFullModalProps) => {
    const { closeModal } = useFullScreenModal();

    return (
        <div className={cn('flex w-full min-h-screen !bg-transparent pt-40 overflow-hidden')}>
            <div className="bg-white w-16 h-16 fixed top-20 z-[3000] right-10 shadow-lg rounded-full flex items-center justify-center cursor-pointer" onClick={closeModal}>
                <Close width="32px" height="40px" stroke="#4D4D4D" strokeWidth={0.8} />
            </div>
            <div className={cn(' w-full bg-white min-h-screen rounded-t-3xl !mt-0 !pt-12 overflow-y-auto scroll-mt-6')}>
                <div className="flex justify-center mx-auto md:w-[600px]">
                    <FormSettingsTab />
                </div>
            </div>
        </div>
    );
};

export default FormSettingFullModalView;
