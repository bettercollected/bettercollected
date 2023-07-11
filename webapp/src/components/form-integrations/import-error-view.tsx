import React, { useState } from 'react';

import Image from 'next/image';

import _ from 'lodash';

import { Disclosure } from '@headlessui/react';
import { CheckCircle, HelpOutline, HourglassEmpty, SyncProblem } from '@mui/icons-material';
import { Checkbox, FormControlLabel, Popover } from '@mui/material';
import PopupState, { bindPopover, bindTrigger } from 'material-ui-popup-state';

import { ChevronDown } from '@app/components/icons/chevron-down';
import { Close } from '@app/components/icons/close';
import ConnectWithProviderButton from '@app/components/login/login-with-google-button';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';

interface ImportErrorViewProps {
    provider: string;
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
    helpText: {
        enable: boolean;
        title?: string;
        info?: Array<string>;
        footer?: string;
        note?: string;
    };
}

interface IDefaultContent {
    type: 'dark' | 'light' | 'typeform';
    permissionText: string;
    authorizeText: string;
    scopes: Array<IScope>;
    permissions: Array<IPermission>;
}

export default function ImportErrorView({ provider }: ImportErrorViewProps) {
    const { closeModal } = useModal();
    const [isConsentGiven, setIsConsentGiven] = useState(false);

    const googlePermissions: Array<IPermission> = [
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'See information about your Google Drive files.',
            description: 'In order for our app to identify and distinguish between form files and other files, we require access to view the names and file types of your Google Drive files',
            helpText: {
                enable: true,
                title: 'Information about your Drive files, includes:',
                info: ['The titles and descriptions of your files', 'The names and email addresses of people you share files with', 'Your folders and how files are organized'],
                footer: 'There may be private information in your Google Drive, like financial records, medical reports, photos or tax info.',
                note: 'BetterCollected will only access the metadata of the available forms in your drive to list them when you are importing the forms.'
            }
        },
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'See all your Google Forms forms.',
            description: 'In order to import forms, we require access to view all the forms created using Google Forms.',
            helpText: {
                enable: true,
                title: 'See all your forms, including:',
                info: ['See and download your forms (including settings and metadata)'],
                footer: 'There may be sensitive information in your forms.'
            }
        },
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: 'See all responses to your Google Forms forms.',
            description: 'This allows us to provide you with the necessary functionality and features to enhance your experience.',
            helpText: {
                enable: true,
                title: 'See all the responses submitted to your forms, including:',
                info: ["respondents' answers to questions", 'quiz grades', 'email addresses of respondents', 'metadata like response dates and times'],
                footer: 'There may be sensitive information in form responses, like birthdays, addresses, and photos.'
            }
        }
    ];
    const typeformPermissions: Array<IPermission> = [
        {
            type: 'non-sensitive',
            isPermissionGiven: true,
            name: "See your personal info, including any personal info you've made publicly available",
            icon: <CheckCircle fontSize="small" color="success" />,
            helpText: {
                enable: false
            }
        },
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: "See all responses to your Typeform's forms.",
            icon: <HourglassEmpty fontSize="small" color="warning" />,
            helpText: {
                enable: true,
                title: 'See all the responses submitted to your forms, including:',
                info: ["respondents' answers to questions", 'email addresses of respondents', 'metadata like response dates and times'],
                footer: 'There may be sensitive information in form responses, like birthdays, addresses, and photos.'
            }
        },
        {
            type: 'sensitive',
            isPermissionGiven: false,
            name: "See all your Typeform's forms.",
            icon: <HourglassEmpty fontSize="small" color="warning" />,
            helpText: {
                enable: true,
                title: 'See all your forms, including:',
                info: ['See and download your forms (including settings and metadata)'],
                footer: 'There may be sensitive information in your forms.'
            }
        }
    ];
    const googleScopes: Array<IScope> = [
        {
            type: 'non-sensitive',
            name: 'openid'
            // url: 'https://developers.google.com/identity/protocols/oauth2/scopes#oauth2'
        },
        {
            type: 'non-sensitive',
            name: 'auth/userinfo.email'
            // url: 'https://developers.google.com/identity/protocols/oauth2/scopes#oauth2'
        },
        {
            type: 'non-sensitive',
            name: 'auth/userinfo.profile'
            // url: 'https://developers.google.com/identity/protocols/oauth2/scopes#oauth2'
        },
        {
            type: 'sensitive',
            name: 'auth/drive.metadata.readonly'
            // url: 'https://developers.google.com/identity/protocols/oauth2/scopes#drive'
        },
        {
            type: 'sensitive',
            name: 'auth/forms.body.readonly'
        },
        {
            type: 'sensitive',
            name: 'auth/forms.responses.readonly'
        }
    ];
    const typeformScopes: Array<IScope> = [
        {
            type: 'non-sensitive',
            name: 'accounts:read',
            url: 'https://www.typeform.com/developers/get-started/scopes/'
        },
        {
            type: 'sensitive',
            name: 'forms:read',
            url: 'https://www.typeform.com/developers/get-started/scopes/'
        },
        {
            type: 'sensitive',
            name: 'responses:read',
            url: 'https://www.typeform.com/developers/get-started/scopes/'
        }
    ];
    const [defaultContent] = useState<IDefaultContent>({
        type: provider === 'google' ? 'dark' : 'typeform',
        permissionText: provider === 'google' ? 'Enable Google Drive Access \n for Form Imports' : '',
        authorizeText: `Please click the button below to provide additional permissions for ${_.capitalize(provider)}.`,
        scopes: provider === 'google' ? googleScopes : typeformScopes,
        permissions: provider === 'google' ? googlePermissions : typeformPermissions
    });

    const getScopeContent = (scope: IScope) => {
        if (scope?.url) {
            return (
                <a target="_blank" rel="noreferrer" className="w-full flex flex-col sm:flex-row hover:text-blue-500 py-2 justify-between border-b-[1px] border-gray-200 last:border-none" key={scope.name} href={scope.url}>
                    <li>{scope.name}</li>
                    <span className={`${scope?.type === 'non-sensitive' ? 'bg-purple-100 text-purple-800' : 'bg-yellow-100 text-yellow-800'} text-xs font-medium mr-2 px-2.5 py-0.5 rounded-full`}>{scope.type}</span>
                </a>
            );
        }
        return (
            <div className="w-full flex flex-col sm:flex-row py-2 justify-between border-b-[1px] border-gray-200 last:border-none" key={scope.name}>
                <li>{scope.name}</li>
                <span className={`${scope?.type === 'non-sensitive' ? 'bg-purple-100 text-purple-800' : 'bg-yellow-100 text-yellow-800'} text-xs font-medium mr-2 px-2.5 py-0.5 rounded-full w-fit`}>{scope.type}</span>
            </div>
        );
    };

    const handleUserConsent = (e: any) => {
        setIsConsentGiven(e.target.checked);
    };

    return (
        <div className="text-sm relative flex items-center justify-center flex-col space-y-5 w-full md:max-w-[500px] rounded-md shadow-md bg-white pb-10">
            <div onClick={() => closeModal()} className="absolute right-3 top-3  cursor-pointer rounded-full p-3">
                <Close className="cursor-pointer" />
            </div>
            <div className="flex flex-col gap-6 mb-6 items-center justify-between">
                <Image src="/drive_logo.png" width={58} height={58} />
                <h2 className="text-black-900 font-semibold text-lg md:text-xl whitespace-pre-wrap text-center">{defaultContent.permissionText}</h2>
            </div>
            {provider === 'google' && (
                <p className="text-black-800 text-[12px] px-4 leading-5 mb-10 text-center">
                    Better Collected Platform&apos;s use and transfer to any other app of information received from Google APIs will adhere to{' '}
                    <a target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400" href="https://developers.google.com/terms/api-services-user-data-policy">
                        Google API Services User Data Policy
                    </a>
                    , including the Limited Use requirements.
                </p>
            )}
            <div className="w-full border-b-[1px]">
                {defaultContent.permissions.map((permission, index) => (
                    <Disclosure key={permission.name} defaultOpen={false}>
                        {({ open }) => (
                            <>
                                <Disclosure.Button className="flex items-center w-full justify-between px-8 py-3 border-t-[1px] text-left body6 font-medium text-black-800 focus:outline-none focus-visible:ring focus-visible:ring-blue-500 focus-visible:ring-opacity-75">
                                    <span>{permission.name}</span>
                                    <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                                </Disclosure.Button>
                                <Disclosure.Panel className="body4 pb-2 -mt-2 pr-8 text-gray-500 w-full">{<div className="px-8">{permission?.description}</div>}</Disclosure.Panel>
                            </>
                        )}
                    </Disclosure>
                ))}
            </div>
            <FormControlLabel
                checked={isConsentGiven}
                onChange={handleUserConsent}
                control={<Checkbox />}
                label={
                    <div className="text-xs">
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
            <ConnectWithProviderButton disabled={!isConsentGiven} type={defaultContent.type} url={`${environments.API_ENDPOINT_HOST}/auth/${provider}/oauth`} text={`Authorize ${_.capitalize(provider)}`} creator />
        </div>
    );
}
