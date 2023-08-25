import React from 'react';

import ConsentAddInput from '@Components/Consent/ConsentAdd';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';

interface CreateConsentContainerProps extends OnlyClassNameInterface {}

export default function CreateConsentContainer({ className }: CreateConsentContainerProps) {
    return (
        <div className={cn('ml-[267px] w-[508px] space-y-20', className)}>
            <div className="space-y-4">
                <div className="h4">Form Purpose and Data Usage</div>
                <div className="p2 !text-[#4D4D4D]">
                    {`We want to make sure you're fully informed about how your data will be used before you proceed with our form. Our commitment to transparency means that we've included a consent page to provide you with important details. Here's what you
        can find on the consent page:`}
                </div>
            </div>
            <div className="space-y-5">
                <div className="h5">Purpose of this form:</div>
                <ConsentAddInput
                    title="Select or Add Purpose"
                    placeholder="Select or Add Purpose"
                    hint={`Help users understand your form's intent! Specify its purpose
            (e.g., marketing, analytics) for transparent consent.`}
                />
            </div>

            <div className="space-y-5">
                <div className="h6">Third-Party Integration:</div>
                <ConsentAddInput
                    title="Select or Add Third-Party Integrations"
                    placeholder="Select or add third-party apps"
                    hint={`Let users know if you're using any third-party apps for form data 
            (e.g., Google Sheets, Google Forms) for transparent consent.`}
                />
            </div>
        </div>
    );
}
