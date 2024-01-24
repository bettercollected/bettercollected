import React from 'react';

import LoginLayout from '@Components/Login/login-layout';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getServerSideProps(_context: any) {
    const config = getServerSideAuthHeaderConfig(_context);
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;

    try {
        const userStatus = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e)) ?? null;

        if (user?.id) {
            const { query } = _context;
            const redirect_to = query.redirect_to;
            if (redirect_to) {
                return {
                    redirect: {
                        permanent: false,
                        destination: redirect_to
                    }
                };
            }
        }

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

    const loginType = _context.query?.type || null;
    const workspace_id = _context.query?.workspace_id || null;
    if (!!loginType !== !!workspace_id) {
        return {
            notFound: true
        };
    }
    return {
        props: { ...globalProps, type: loginType, workspace_id }
    };
}

export const Login = ({ type = 'creator', workspace_id }: { type?: string; workspace_id?: string }) => {
    return <LoginLayout isCreator={type !== 'responder'} workspaceId={workspace_id} />;
};

export default Login;
