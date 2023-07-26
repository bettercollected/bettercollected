import React from 'react';

import { useTranslation } from 'next-i18next';

import LoginLayout from '@Components/Login/login-layout';

import environments from '@app/configs/environments';
import { signInScreen } from '@app/constants/locales/signin-screen';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getServerSideProps(_context: any) {
    const config = getServerSideAuthHeaderConfig(_context);
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;
    if (checkHasCustomDomain(_context)) {
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    }

    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e)) ?? null;
        if (user?.roles?.includes('FORM_CREATOR')) {
            const userWorkspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/mine`, config);
            const userWorkspace = (await userWorkspaceResponse?.json().catch((e: any) => e)) ?? null;
            const defaultWorkspace = userWorkspace.filter((workspace: WorkspaceDto) => workspace.ownerId === user.id && workspace?.default);
            let redirectWorkspace: WorkspaceDto | null;
            if (defaultWorkspace.length > 0) {
                redirectWorkspace = defaultWorkspace[0];
            } else {
                redirectWorkspace = userWorkspace[0];
            }
            if (!redirectWorkspace?.title || redirectWorkspace?.title === '' || redirectWorkspace?.title.toLowerCase() === 'untitled') {
                return {
                    redirect: {
                        permanent: false,
                        destination: `/${locale}${redirectWorkspace?.workspaceName}/onboarding`
                    }
                };
            }
            return {
                redirect: {
                    permanent: false,
                    destination: `/${locale}${redirectWorkspace?.workspaceName}/dashboard`
                }
            };
        }
    } catch (e) {
        console.error(e);
    }
    return {
        props: { ...globalProps }
    };
}

export const Login = () => {
    const { t } = useTranslation();

    const constants = {
        heading: t(signInScreen.features.title),
        paragraphs: [t(signInScreen.features.feature1), t(signInScreen.features.feature2), t(signInScreen.features.feature3), t(signInScreen.features.feature4), t(signInScreen.features.feature5), t(signInScreen.features.feature6)]
    };

    return <LoginLayout isCreator={true} features={constants} />;
};

export default Login;
