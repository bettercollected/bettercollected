import { useState } from 'react';

import { TextField } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';

export default function MySettings() {
    const [customUrl, setCustomUrl] = useState('');
    const [error, setError] = useState(false);

    const { openModal } = useModal();

    const Header = () => {
        return (
            <div className="w-full flex justify-between items-center pb-4 border-b-gray-200 mb-4 border-b-[1px]">
                <div>
                    <h1 className="font-semibold text-2xl">Settings</h1>
                    <p className="text-gray-600"> Manage your form settings and preferences.</p>
                </div>

                <Button onClick={() => openModal('EDIT_WORKSPACE_VIEW')} className="!rounded-md !inline-block !bg-blue-500" size="medium">
                    Edit workspace info
                </Button>
            </div>
        );
    };

    return (
        <Layout>
            <Header />
            <div className="flex justify-between items-center">
                <div className={`text-xl font-bold w-full text-black `}>Custom Domain</div>
                <div className="w-full">
                    <TextField
                        size="medium"
                        name="search-input"
                        placeholder="Custom-domain (e.g. https://forms.bettercollected.com)"
                        value={customUrl}
                        error={error}
                        onChange={(event) => {
                            if (event.target.value && !event.target.value.match('^\\S+$')) {
                                setError(true);
                            } else {
                                setError(false);
                            }
                            setCustomUrl(event.target.value);
                        }}
                        className={`w-full`}
                    />
                    <div className="text-red-500 text-sm">{error && 'Custom Domain cannot contain spaces.'}</div>
                </div>
            </div>
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    const { cookies } = _context.req;
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    if (globalProps.hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.payload?.content ?? null;
        if (!user?.user?.roles?.includes('FORM_CREATOR')) {
            return {
                redirect: {
                    permanent: false,
                    destination: '/login'
                }
            };
        }
    } catch (e) {
        return {
            redirect: {
                permanent: false,
                destination: '/login'
            }
        };
    }
    return {
        props: {
            ...globalProps
        }
    };
}
