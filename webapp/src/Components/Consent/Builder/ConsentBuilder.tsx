import React from 'react';

import FormButton from '@Components/Common/Input/Button/FormButton';
import { CheckBox } from '@mui/icons-material';
import cn from 'classnames';

import { dataRetention, formPurpose, thirdPartySharing } from '@app/data/consent';
import { OnlyClassNameInterface } from '@app/models/interfaces';

import ConsentAddInput from './ConsentAdd';
import ConsentInput from './ConsentInput';

interface ConsentBuilderProps extends OnlyClassNameInterface {}

export default function ConsentBuilder({ className }: ConsentBuilderProps) {
    const formPurposeDetails = (
        <>
            <div className="space-y-5">
                <div className="h4-new">Purpose of this form:</div>
                <ConsentAddInput title={formPurpose.title} placeholder="Select or Add Purpose" hint={formPurpose.hint} options={formPurpose.options} />
            </div>
        </>
    );

    const thirdPartyIntegrationDetails = (
        <>
            <div className="space-y-5">
                <div className="h4-new">Third-Party Integration:</div>
                <ConsentAddInput title={thirdPartySharing.title} placeholder="Select or add third-party apps" hint={thirdPartySharing.hint} options={thirdPartySharing.options} />
            </div>
        </>
    );

    const dataRetentionDetails = (
        <>
            <div className="space-y-5">
                <div className="h4-new">For how long data will be stored:</div>
                <ConsentAddInput title={dataRetention.title} placeholder="Select a Data Retention options" hint={dataRetention.hint} options={dataRetention.options} />
            </div>
        </>
    );

    const responderRightDetails = (
        <>
            <div className="space-y-5">
                <div className="space-y-5">
                    <div className="h4-new">{`Responder's Rights`}</div>
                    <div className="flex space-x-2">
                        <CheckBox sx={{ color: '#0764EB' }} />{' '}
                        <div className="space-y-2">
                            <div className="h6-new">Request deletion of their data</div>
                            <p className="p2">This field allows you to specify whether you will allow users to request the deletion of their data and other actions.</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );

    return (
        <form className={cn(className)}>
            <div className="space-y-20">
                <div className="space-y-4">
                    <div className="h4">Form Purpose and Data Usage</div>
                    <div className="p2 !text-new-black-800">
                        {`We want to make sure you're fully informed about how your data will be used before you proceed with our form. Our commitment to transparency means that we've included a consent page to provide you with important details. Here's what you
        can find on the consent page:`}
                    </div>
                </div>
                {formPurposeDetails}
                {thirdPartyIntegrationDetails}
                {dataRetentionDetails}
                {responderRightDetails}
                <div>
                    <div className="h4-new">Terms and Conditions</div>
                    <ConsentInput type="file" title="Insert Link to Your Terms And Conditions" placeholder="Insert link here" className="mt-5" />
                </div>
            </div>
            <FormButton className="w-[192px] mt-[60px]">Done</FormButton>
        </form>
    );
}
