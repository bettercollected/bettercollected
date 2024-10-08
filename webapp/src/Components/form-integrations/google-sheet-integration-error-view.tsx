import React, { useState } from 'react';

import _ from 'lodash';

import CheckedCircle from '@Components/Common/Icons/Common/CheckedCircle';
import CloseModal from '@Components/Modals/CloseModal';
import { Disclosure } from '@headlessui/react';
import { Checkbox, FormControlLabel } from '@mui/material';

import { ChevronDown } from '@app/Components/icons/chevron-down';
import ConnectWithProviderButton from '@app/Components/Login/login-with-google-button';
import environments from '@app/configs/environments';

interface ImportErrorViewProps {
    closable?: boolean;
}

interface IScope {
    type?: string;
    name: string;
    url?: string;
}

interface IPermission {
    type?: string;
    name: string;
    icon?: React.ReactNode;
    isPermissionGiven: boolean;
    description?: string;
    scope?: string;
}

export default function GoogleSheetIntegrationErrorView({ closable = true }: ImportErrorViewProps) {
    const [isConsentGiven, setIsConsentGiven] = useState(false);

    const googlePermissions: Array<IPermission> = [
        {
            type: 'non-sensitive',
            isPermissionGiven: false,
            name: 'Permission to read and write in Google Sheets',
            description: 'To be able to write in Google Sheets, we require permissions to search your Google Drive for Google Sheets.',
            scope: 'https://www.googleapis.com/auth/drive.file'
        }
    ];

    const [defaultContent] = useState<IDefaultContent>({
        type: 'dark',
        permissionText: 'Enable Permissions for Integrating with\n' + 'Google Sheets',
        permissions: googlePermissions
    });

    const handleUserConsent = (e: any) => {
        setIsConsentGiven(e.target.checked);
    };

    return (
        <div className="relative flex w-full flex-col items-center justify-center space-y-5 rounded-md bg-white py-10 text-sm shadow-md md:max-w-[560px]">
            {closable && <CloseModal />}
            <div className="!mt-0 flex flex-col items-center justify-between">
                <CheckedCircle />
                <h2 className="text-black-900 mt-6 whitespace-pre-wrap text-center text-lg font-semibold md:text-xl">{defaultContent.permissionText}</h2>
            </div>

            <div className="w-full border-b-[1px]">
                {defaultContent.permissions.map((permission, index) => (
                    <Disclosure key={permission.name} defaultOpen={false}>
                        {({ open }) => (
                            <>
                                <Disclosure.Button className="body6 text-black-800 flex w-full items-center justify-between border-t-[1px] px-8 py-3 text-left font-medium focus:outline-none focus-visible:ring focus-visible:ring-blue-500 focus-visible:ring-opacity-75">
                                    {permission.name}
                                    <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                                </Disclosure.Button>
                                <Disclosure.Panel className="body4 -mt-2 w-full pb-2 pr-8 text-gray-500">{<div className="px-8">{permission?.description}</div>}</Disclosure.Panel>
                            </>
                        )}
                    </Disclosure>
                ))}
            </div>
            <p className="text-black-800 px-8 text-left text-[12px] leading-5">
                Better Collected Platform&apos;s use and transfer to any other app of information received from Google APIs will adhere to{' '}
                <a target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400" href="https://developers.google.com/terms/api-services-user-data-policy">
                    Google API Services User Data Policy
                </a>
                , including the Limited Use requirements.
            </p>
            <div className="!mt-3 flex w-full px-8">
                <FormControlLabel
                    checked={isConsentGiven}
                    onChange={handleUserConsent}
                    control={<Checkbox />}
                    label={
                        <div className="body4">
                            By signing in, you agree to our{' '}
                            <a href="https://bettercollected.com/terms-of-service/" target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400">
                                Terms of Service
                            </a>{' '}
                            and{' '}
                            <a href="https://bettercollected.com/privacy-policy/" target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400">
                                Privacy Policy
                            </a>
                            .
                        </div>
                    }
                />
            </div>
            <div className="w-[230px]">
                <ConnectWithProviderButton disabled={!isConsentGiven} type={defaultContent.type} url={`${environments.API_ENDPOINT_HOST}/auth/google/oauth?integration=google-sheets`} text={`Authorize ${_.capitalize('google')}`} creator />
            </div>
        </div>
    );
}

interface IDefaultContent {
    type: 'dark' | 'light' | 'typeform';
    permissionText: string;
    permissions: Array<IPermission>;
}
