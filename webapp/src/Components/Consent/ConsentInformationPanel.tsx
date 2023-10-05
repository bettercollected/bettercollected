import React, { useEffect, useState } from 'react';

import { Close } from '@app/components/icons/close';
import { Hint } from '@app/components/icons/hint';
import { consentPageInformation } from '@app/data/consent';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';

export default function ConsentInformationPanel() {
    const [isOpen, setOpen] = useState(false);

    const isMobile = useIsMobile();

    const getTitleDescription = (title = '', description: string) => {
        return (
            <div className="space-y-2">
                {title.length !== 0 && <div className="h4-new">{title}</div>}
                <p className="p2 !text-new-black-800">{description}</p>
            </div>
        );
    };

    useEffect(() => {
        if (!isMobile) {
            setOpen(true);
        }
    }, [isMobile]);

    if (!isOpen)
        return (
            <div className="flex space-x-1 cursor-pointer absolute right-0 items-center z-[1000] pt-3 px-6" onClick={() => setOpen(true)}>
                <Hint />
                <span className="p2 !text-new-black-800">What is this page?</span>
            </div>
        );
    return (
        <div className="bg-new-blue-100 px-6 xs:px-4 py-5 h-full w-[397px] space-y-10  z-[1000] absolute right-0">
            <div className="space-y-4 relative">
                <Close className="absolute right-0 -top-2 cursor-pointer" onClick={() => setOpen(false)} />
                <div className="h4-new">{consentPageInformation.title}</div>
                {getTitleDescription('', consentPageInformation.description)}
            </div>
            <div className="space-y-4">
                <div className="h4-new">{consentPageInformation.importanceTitle}</div>
                {consentPageInformation.importanceDescription.map((description) => getTitleDescription(description.title, description.description))}
            </div>
        </div>
    );
}
