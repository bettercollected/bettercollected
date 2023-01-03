import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import environments from '@app/configs/environments';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { checkHasCustomDomain, checkIfUserIsAuthorizedToViewPage } from '@app/utils/serverSidePropsUtils';

export default async function getServerSideProps({ locale, ..._context }: any): Promise<{
    props: IServerSideProps;
}> {
    // const hasCustomDomain = !!environments.IS_CUSTOM_DOMAIN;
    const hasCustomDomain = checkHasCustomDomain(_context);
    // let workspaceId: string | null = null;
    const workspaceId = environments.WORKSPACE_ID;
    let workspace: WorkspaceDto | null = null;
    try {
        if (hasCustomDomain && workspaceId) {
            const workspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}`).catch((e) => e);
            workspace = (await workspaceResponse?.json().catch((e: any) => e)) ?? null;
        }
    } catch (err) {
        workspace = null;
        console.error(err);
    }
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
            hasCustomDomain,
            workspaceId,
            workspace
        }
    };
}

export async function getGlobalServerSidePropsByDomain({ locale, ..._context }: any): Promise<{
    props: IServerSideProps;
}> {
    const domain = _context.req.headers.host;

    const hasCustomDomain = domain !== environments.CLIENT_HOST;
    let workspaceId = '';
    let workspace = null;

    if (!hasCustomDomain) {
        return {
            props: {
                ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
                hasCustomDomain,
                workspaceId,
                workspace
            }
        };
    }
    try {
        const workspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`).catch((e) => e);
        workspace = (await workspaceResponse?.json().catch((e: any) => e)) ?? null;
        workspaceId = workspace.id;
    } catch (e) {}

    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
            hasCustomDomain,
            workspaceId,
            workspace
        }
    };
}

export async function getGlobalServerSidePropsByWorkspaceName({ locale, ..._context }: any): Promise<
    | {
          props: IServerSideProps;
      }
    | any
> {
    const hasCustomDomain = checkHasCustomDomain(_context);
    let workspaceId = '';
    let workspace = null;
    const { workspace_name } = _context.params;

    if (!workspace_name) {
        return {
            props: {
                ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
                hasCustomDomain,
                workspaceId,
                workspace
            }
        };
    }
    try {
        const workspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces?workspace_name=${workspace_name}`).catch((e) => e);
        workspace = (await workspaceResponse?.json().catch((e: any) => e)) ?? null;
        workspaceId = workspace.id;
    } catch (e) {}
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
            hasCustomDomain,
            workspaceId,
            workspace
        }
    };
}

export async function getAuthUserPropsWithWorkspace(_context: any) {
    const hasCustomDomain = checkHasCustomDomain(_context);
    if (hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    if (!globalProps.workspace.id) {
        return {
            notFound: true
        };
    }
    if (!(await checkIfUserIsAuthorizedToViewPage(_context, globalProps.workspace)))
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    return {
        props: {
            ...globalProps
        }
    };
}
