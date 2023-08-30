import React, { useState } from 'react';

import { Close } from '@app/components/icons/close';
import { Hint } from '@app/components/icons/hint';
import { consentPageInformation } from '@app/data/consent';

export default function ConsentInformationPanel() {
    const [isOpen, setOpen] = useState(true);

    const getTitleDescription = (title = '', description: string) => {
        return (
            <div className="space-y-2">
                {title.length !== 0 && <div className="h5-new">{title}</div>}
                <p className="p2 !text-new-black-800">{description}</p>
            </div>
        );
    };

    if (!isOpen)
        return (
            <div className="flex space-x-1 cursor-pointer fixed right-0 items-center py-6 px-6" onClick={() => setOpen(true)}>
                <Hint />
                <span className="p2 !text-new-black-800">What is this page?</span>
            </div>
        );
    return (
        <div className="bg-new-blue-100 px-6 xs:px-[15px] py-5 h-full w-[397px] space-y-10 fixed right-0">
            <div className="space-y-4 relative">
                <Close className="absolute right-0 -top-2 cursor-pointer" onClick={() => setOpen(false)} />
                <div className="h5-new">{consentPageInformation.title}</div>
                {getTitleDescription('', consentPageInformation.description)}
            </div>
            <div className="space-y-4">
                <div className="h5-new">{consentPageInformation.importanceTitle}</div>
                {consentPageInformation.importanceDescription.map((description) => getTitleDescription(description.title, description.description))}
            </div>
        </div>
    );
}
