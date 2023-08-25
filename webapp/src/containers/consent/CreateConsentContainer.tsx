import React from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import ConsentAddInput from '@Components/Consent/ConsentAdd';
import cn from 'classnames';

import { OnlyClassNameInterface } from '@app/models/interfaces';

interface CreateConsentContainerProps extends OnlyClassNameInterface {}

export default function CreateConsentContainer({ className }: CreateConsentContainerProps) {
    return (
        <div className={cn('ml-[267px] w-[508px]', className)}>
            <div className="space-y-20">
                <div className="space-y-4">
                    <div className="h4">Form Purpose and Data Usage</div>
                    <div className="p2 !text-new-black-800">
                        {`We want to make sure you're fully informed about how your data will be used before you proceed with our form. Our commitment to transparency means that we've included a consent page to provide you with important details. Here's what you
        can find on the consent page:`}
                    </div>
                </div>
                <div className="space-y-5">
                    <div className="h4-new">Purpose of this form:</div>
                    <ConsentAddInput
                        title="Select or Add Purpose"
                        placeholder="Select or Add Purpose"
                        hint={`Help users understand your form's intent! Specify its purpose
            (e.g., marketing, analytics) for transparent consent.`}
                    />
                </div>

                <div className="space-y-5">
                    <div className="h4-new">Third-Party Integration:</div>
                    <ConsentAddInput
                        title="Select or Add Third-Party Integrations"
                        placeholder="Select or add third-party apps"
                        hint={`Let users know if you're using any third-party apps for form data 
            (e.g., Google Sheets, Google Forms) for transparent consent.`}
                    />
                </div>

                <div className="space-y-5">
                    <div className="h4-new">For how long data will be stored:</div>
                    <ConsentAddInput title="Data Retention options" placeholder="Select a Data Retention options" hint={`Inform users about data retention. Customize how long user data will be stored and whether users can request deletion.`} />
                </div>
            </div>
            <FormButton className="w-[192px] mt-[60px]">Done</FormButton>
        </div>
    );
}
