import React, { useState } from 'react';

import _ from 'lodash';

import CheckedCircle from '@Components/Common/Icons/Common/CheckedCircle';
import CloseModal from '@Components/Modals/CloseModal';
import { Disclosure } from '@headlessui/react';
import { Checkbox, FormControlLabel } from '@mui/material';

import { ChevronDown } from '@app/components/icons/chevron-down';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import environments from '@app/configs/environments';

interface ImportErrorViewProps {
    provider: string;
    closable?: boolean;
    unauthorizedScopes?: Array<string>;
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

interface IDefaultContent {
    type: 'dark' | 'light' | 'typeform';
    permissionText: string;
    permissions: Array<IPermission>;
}

export default function ImportErrorView({ provider, closable = true, unauthorizedScopes }: ImportErrorViewProps) {
    const [isConsentGiven, setIsConsentGiven] = useState(false);

    const googlePermissions: Array<IPermission> = [
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'Permissions to import your Google Forms',
            description: 'To be able to import forms from Google, we require access permissions to retrieve your Google Forms.',
            scope: 'https://www.googleapis.com/auth/forms.body.readonly'
        },
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'Permissions to import form responses',
            description: 'To be able to show form responses and build a beautiful responder portal for you, we require permissions to fetch form responses.',
            scope: 'https://www.googleapis.com/auth/forms.responses.readonly'
        }
    ];

    if (environments.ENABLE_IMPORT_WITH_PICKER) {
        googlePermissions.splice(0, 0, {
            type: 'non-sensitive',
            isPermissionGiven: false,
            name: 'Permission to search and pick Google Forms from Drive',
            description: 'To be able to show Google File Picker, we require permissions to search your Google Drive for Google Forms.',
            scope: 'https://www.googleapis.com/auth/drive.file'
        });
    }
    const typeformPermissions: Array<IPermission> = [
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'Permissions to import your Typeform',
            description: 'To be able to show a list of forms for you to import, we require permissions to fetch Typeforms.'
        },
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'Permissions to import form responses',
            description: 'To be able to show form responses and build a beautiful responder portal for you, we require permissions to fetch form responses.'
        }
    ];
    const [defaultContent] = useState<IDefaultContent>({
        type: provider === 'google' ? 'dark' : 'typeform',
        permissionText: provider === 'google' ? 'Enable Permissions for Importing\n' + 'Google Forms' : 'Enable Permissions for Importing\n' + 'Typeform',
        permissions: provider === 'google' ? googlePermissions : typeformPermissions
    });

    const handleUserConsent = (e: any) => {
        setIsConsentGiven(e.target.checked);
    };

    return (
        <div className="text-sm relative flex items-center justify-center flex-col space-y-5 w-full md:max-w-[560px] rounded-md shadow-md bg-white py-10">
            {closable && <CloseModal />}
            <div className="flex flex-col !mt-0 items-center justify-between">
                <CheckedCircle />
                <h2 className="text-black-900 font-semibold mt-6 text-lg md:text-xl whitespace-pre-wrap text-center">{defaultContent.permissionText}</h2>
            </div>

            <div className="w-full border-b-[1px]">
                {defaultContent.permissions.map((permission, index) => (
                    <Disclosure key={permission.name} defaultOpen={false}>
                        {({ open }) => (
                            <>
                                <Disclosure.Button className="flex items-center w-full justify-between px-8 py-3 border-t-[1px] text-left body6 font-medium text-black-800 focus:outline-none focus-visible:ring focus-visible:ring-blue-500 focus-visible:ring-opacity-75">
                                    <span>
                                        {unauthorizedScopes && unauthorizedScopes.length > 0 && <span className={`text-lg mr-2 ${unauthorizedScopes?.includes(permission.scope || '') ? 'text-black-400' : 'text-green-500'}`}>✔</span>}
                                        {permission.name}
                                    </span>
                                    <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                                </Disclosure.Button>
                                <Disclosure.Panel className="body4 pb-2 -mt-2 pr-8 text-gray-500 w-full">{<div className="px-8">{permission?.description}</div>}</Disclosure.Panel>
                            </>
                        )}
                    </Disclosure>
                ))}
            </div>
            {provider === 'google' && (
                <p className="text-black-800 text-[12px] px-8 leading-5 text-left">
                    Better Collected Platform&apos;s use and transfer to any other app of information received from Google APIs will adhere to{' '}
                    <a target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400" href="https://developers.google.com/terms/api-services-user-data-policy">
                        Google API Services User Data Policy
                    </a>
                    , including the Limited Use requirements.
                </p>
            )}
            <div className="flex w-full !mt-3 px-8">
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
                <ConnectWithProviderButton disabled={!isConsentGiven} type={defaultContent.type} url={`${environments.API_ENDPOINT_HOST}/auth/${provider}/oauth`} text={`Authorize ${_.capitalize(provider)}`} creator />
            </div>
        </div>
    );
}
