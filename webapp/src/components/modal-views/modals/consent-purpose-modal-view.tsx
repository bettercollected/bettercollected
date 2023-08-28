import React from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import TextArea from '@Components/Common/Input/TextArea';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';

export default function ConsentPurposeModalView() {
    return (
        <div>
            <div className="flex justify-between py-4 px-6">
                <div className="p2 !text-black-800">Purpose Of The Form</div>
                <DropdownCloseIcon />
            </div>
            <div className="pt-6 px-10 pb-10 space-y-10">
                <div className="h3-new">Marketing</div>

                <div className="space-y-2">
                    <div className="h5-new">Brief description of your purpose</div>
                    <TextArea placeholder="Enter text here" />
                </div>
            </div>
            <AppButton className="w-[192px]">Add</AppButton>
        </div>
    );
}
