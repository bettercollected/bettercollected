import { useState } from 'react';

import _ from 'lodash';

import { Disclosure } from '@headlessui/react';
import { SyncProblem } from '@mui/icons-material';

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

interface IDefaultContent {
    type: 'dark' | 'light' | 'typeform';
    permissionText: string;
    authorizeText: string;
    scopes: Array<IScope>;
}

export default function ImportErrorView({ provider }: ImportErrorViewProps) {
    const { closeModal } = useModal();
    const googleScopes = [
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
    const typeformScopes = [
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
        scopes: provider === 'google' ? googleScopes : typeformScopes
    });

    const getScopeContent = (scope: IScope) => {
        if (scope?.url) {
            return (
                <a target="_blank" rel="noreferrer" className="w-full flex hover:text-blue-500 py-2 justify-between border-b-[1px] border-gray-200 last:border-none" key={scope.name} href={scope.url}>
                    <li>{scope.name}</li>
                    <span className={`${scope?.type === 'non-sensitive' ? 'bg-purple-100 text-purple-800' : 'bg-yellow-100 text-yellow-800'} text-xs font-medium mr-2 px-2.5 py-0.5 rounded-full`}>{scope.type}</span>
                </a>
            );
        }
        return (
            <div className="w-full flex py-2 justify-between border-b-[1px] border-gray-200 last:border-none" key={scope.name}>
                <li>{scope.name}</li>
                <span className={`${scope?.type === 'non-sensitive' ? 'bg-purple-100 text-purple-800' : 'bg-yellow-100 text-yellow-800'} text-xs font-medium mr-2 px-2.5 py-0.5 rounded-full`}>{scope.type}</span>
            </div>
        );
    };

    return (
        <div className="text-sm relative py-10 px-10 flex items-center justify-center flex-col space-y-5 w-full md:w-[480px] p-4 rounded-md shadow-md bg-white">
            <div onClick={() => closeModal()} className="border-[1.5px] absolute right-5 top-5 border-gray-200 hover:shadow hover:text-black cursor-pointer rounded-full p-3">
                <Close className="cursor-pointer text-gray-600 hover:text-black" />
            </div>
            <SyncProblem className="w-[70px] h-[70px] text-red-600" />
            <h2 className="text-gray-700 text-xl text-center">{defaultContent.permissionText}</h2>
            <h6 className="text-gray-500 text-center">{defaultContent.authorizeText}</h6>
            <ConnectWithProviderButton type={defaultContent.type} url={`${environments.API_ENDPOINT_HOST}/auth/${provider}/oauth`} text={_.capitalize(provider)} creator />
            <Disclosure>
                {({ open }) => (
                    <>
                        <Disclosure.Button className="flex w-full justify-between rounded-lg bg-purple-100 px-4 py-2 text-left text-sm font-medium text-purple-900 hover:bg-purple-200 focus:outline-none focus-visible:ring focus-visible:ring-purple-500 focus-visible:ring-opacity-75">
                            <span>See all the required permissions</span>
                            <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-5 w-5 text-purple-500`} />
                        </Disclosure.Button>
                        <Disclosure.Panel className="px-4 pt-2 pb-2 text-sm text-gray-500 w-full">
                            <ol className="list-decimal ml-4">{defaultContent.scopes.map((scope) => getScopeContent(scope))}</ol>
                        </Disclosure.Panel>
                    </>
                )}
            </Disclosure>
            {provider === 'google' && (
                <p className="text-gray-500 text-xs text-center">
                    Better Collected Platform&apos;s use and transfer to any other app of information received from Google APIs will adhere to{' '}
                    <a target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-400" href="https://developers.google.com/terms/api-services-user-data-policy">
                        Google API Services User Data Policy
                    </a>
                    , including the Limited Use requirements.
                </p>
            )}
        </div>
    );
}
