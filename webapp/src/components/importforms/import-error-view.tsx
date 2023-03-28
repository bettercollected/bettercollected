import { useState } from 'react';

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
    icon: React.ReactNode;
    isPermissionGiven: boolean;
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
            name: 'See information about your Google Drive files.',
            icon: <HourglassEmpty fontSize="small" color="warning" />,
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
            icon: <HourglassEmpty fontSize="small" color="warning" />,
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
            icon: <HourglassEmpty fontSize="small" color="warning" />,
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
        permissionText: 'We require additional permissions before you can start importing the forms.',
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
        <div className="text-sm relative py-10 px-10 flex items-center justify-center flex-col space-y-5 w-full md:max-w-[500px] p-4 rounded-md shadow-md bg-white">
            <div onClick={() => closeModal()} className="border-[1.5px] absolute right-5 top-5 border-gray-200 hover:shadow hover:text-black cursor-pointer rounded-full p-3">
                <Close className="cursor-pointer text-gray-600 hover:text-black" />
            </div>
            <div className="flex gap-2 items-center justify-between">
                <SyncProblem className="hidden md:block md:w-[40px] md:h-[40px] text-orange-400" />
                <h2 className="text-gray-800 text-lg md:text-xl text-center">{defaultContent.permissionText}</h2>
            </div>
            {provider === 'google' && (
                <p className="text-gray-500 text-xs text-center">
                    Better Collected Platform&apos;s use and transfer to any other app of information received from Google APIs will adhere to{' '}
                    <a target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400" href="https://developers.google.com/terms/api-services-user-data-policy">
                        Google API Services User Data Policy
                    </a>
                    , including the Limited Use requirements.
                </p>
            )}

            <Disclosure defaultOpen>
                {({ open }) => (
                    <>
                        <Disclosure.Button className="flex items-center w-full justify-between rounded-lg bg-blue-100 px-4 py-2 text-left text-sm font-medium text-blue-900 hover:bg-blue-200 focus:outline-none focus-visible:ring focus-visible:ring-blue-500 focus-visible:ring-opacity-75">
                            <span>See all the required permissions</span>
                            <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                        </Disclosure.Button>
                        <Disclosure.Panel className="pt-2 pb-2 text-sm text-gray-500 w-full">
                            <ol className="list-decimal flex flex-col gap-2">
                                {defaultContent.permissions.map((permission) => (
                                    <div key={permission.name} className="flex w-full justify-start gap-6 items-center border-b-[1px] border-gray-200 pb-1 last:border-none">
                                        {permission.icon}
                                        <span>{permission.name}</span>
                                        {!permission.isPermissionGiven && permission.helpText.enable && (
                                            <div className="ml-auto">
                                                <PopupState variant="popover" popupId={permission.name}>
                                                    {(popupState) => (
                                                        <div>
                                                            <span className="text-blue-500" {...bindTrigger(popupState)}>
                                                                <HelpOutline />
                                                            </span>
                                                            <Popover
                                                                {...bindPopover(popupState)}
                                                                anchorOrigin={{
                                                                    vertical: 'bottom',
                                                                    horizontal: 'right'
                                                                }}
                                                                transformOrigin={{
                                                                    vertical: 'top',
                                                                    horizontal: 'right'
                                                                }}
                                                            >
                                                                <div className="text-xs text-gray-500 p-4 max-w-xs md:max-w-md flex flex-col gap-4">
                                                                    <p>{permission?.helpText?.title}</p>
                                                                    <ul className="list-disc">
                                                                        {permission?.helpText?.info?.map((info, idx) => (
                                                                            <li className="ml-6" key={idx}>
                                                                                {info}
                                                                            </li>
                                                                        ))}
                                                                    </ul>
                                                                    <p>{permission?.helpText?.footer}</p>
                                                                    {permission?.helpText?.note && <p className="font-bold text-gray-800">{permission?.helpText?.note}</p>}
                                                                </div>
                                                            </Popover>
                                                        </div>
                                                    )}
                                                </PopupState>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </ol>
                        </Disclosure.Panel>
                    </>
                )}
            </Disclosure>

            <p className="text-gray-700 text-xs text-center">{defaultContent.authorizeText}</p>
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
            <Disclosure>
                {({ open }) => (
                    <>
                        <Disclosure.Button className="flex items-center w-full justify-between rounded-lg bg-purple-100 px-4 py-2 text-left text-sm font-medium text-purple-900 hover:bg-purple-200 focus:outline-none focus-visible:ring focus-visible:ring-purple-500 focus-visible:ring-opacity-75">
                            <span>See all the required permission scopes</span>
                            <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-purple-900`} />
                        </Disclosure.Button>
                        <Disclosure.Panel className="px-4 pt-2 pb-2 text-sm text-gray-500 w-full">
                            <ol className="list-decimal ml-4">{defaultContent.scopes.map((scope) => getScopeContent(scope))}</ol>
                        </Disclosure.Panel>
                    </>
                )}
            </Disclosure>
        </div>
    );
}
