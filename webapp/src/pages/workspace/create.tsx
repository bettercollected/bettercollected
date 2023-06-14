import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import environments from '@app/configs/environments';
import Onboarding from '@app/pages/[workspace_name]/onboarding';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getServerSideProps({ locale, ..._context }: any) {
    const config = getServerSideAuthHeaderConfig(_context);
    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
        if (!user?.roles?.includes('FORM_CREATOR') || user?.plan !== 'PRO') {
            return {
                redirect: {
                    permanent: false,
                    destination: '/'
                }
            };
        }
    } catch (e) {
        return {
            props: {
                ...(await serverSideTranslations(locale, ['common'], null, ['en', 'nl']))
            }
        };
    }

    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'nl']))
        }
    };
}

export default function CreateWorkspace() {
    return <Onboarding createWorkspace />;
}
