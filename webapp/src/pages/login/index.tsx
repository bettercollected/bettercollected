import React from 'react';

import ResponderLoginPage from '@Components/Login/ResponderLoginPage';
import LoginLayout from '@Components/Login/login-layout';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { checkHasAdminDomain, getRequestHost, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getServerSideProps(_context: any) {
    const config = getServerSideAuthHeaderConfig(_context);
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;

    const hasAdminDomain = checkHasAdminDomain(getRequestHost(_context));

    const loginType = _context.query?.type || null;
    const workspace_id = _context.query?.workspace_id || null;
    const redirect_to = _context.query?.redirect_to || null;

    if (!hasAdminDomain && (!loginType || !workspace_id)) {
        return {
            notFound: true
        };
    }

    if (!hasAdminDomain) {
        return {
            props: { ...globalProps, type: loginType, workspace_id, redirect_to }
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
                    destination: `/${locale}${redirectWorkspace?.workspaceName}/dashboard/forms`
                }
            };
        }
    } catch (e) {
        console.error(e);
    }

    return {
        props: { ...globalProps, type: loginType, workspace_id, redirect_to }
    };
}

export const Login = ({ type = 'creator', workspace_id, redirect_to }: { type?: string; workspace_id?: string; redirect_to?: string }) => {
    const isAdminDomain = window?.location?.host === environments.ADMIN_DOMAIN;

    if (!isAdminDomain && workspace_id && redirect_to) return <ResponderLoginPage workspaceId={workspace_id} redirectTo={redirect_to} />;

    return <LoginLayout isCreator={type !== 'responder'} workspaceId={workspace_id} />;
};

export default Login;
