import React, { useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import MuiSwitch from '@Components/Common/Input/Switch';
import TextArea from '@Components/Common/Input/TextArea';
import { event } from 'cypress/types/jquery';
import ContentEditable from 'react-contenteditable';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';

import { useModal } from '../context';

export default function ConsentPurposeModalView() {
    const [purposeTitle, setPurposeTitle] = useState('');
    const { closeModal } = useModal();

    const handlePurposeTitleChange = (event: any) => {
        setPurposeTitle(event.target.value);
    };
    return (
        <div className="bg-white rounded-2xl w-[621px] h-content">
            <div className="flex justify-between py-4 px-6 border-b border-black-200">
                <div className="p2 !text-black-800">Purpose Of The Form</div>
                <DropdownCloseIcon className="cursor-pointer" onClick={closeModal} />
            </div>
            <div className="pt-6  pb-10 space-y-10">
                <ContentEditable className="h3-new m-0 p-0 w-full cursor-text focus-visible:border-0 focus-visible:outline-none px-10" html={purposeTitle} data-placeholder="Add Purpose" onChange={handlePurposeTitleChange} />

                <div className="space-y-2 px-10">
                    <div className="h5-new">Brief description of your purpose</div>
                    <TextArea placeholder="Enter text here" minRows={4} />
                </div>

                <div className="flex justify-between bg-blue-100 px-10 py-6">
                    <div className="space-y-3">
                        <div className="h5-new">Make this purpose required (*)</div>
                        <p className="p2 !text-black-800">Enabling this option will make the purpose section mandatory (*). Users filling out the form must accept this purpose and acknowledge it.</p>
                    </div>
                    <MuiSwitch thumbSize={24} trackColorUnchecked="#AAAAAA" />
                </div>
                <div className="px-10">
                    <AppButton className="w-[192px] py-3 px-8 bg-new-blue-500">Add</AppButton>
                </div>
            </div>
        </div>
    );
}
