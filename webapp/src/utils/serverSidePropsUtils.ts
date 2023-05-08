import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export function checkHasCustomDomain(_context: any) {
    const forwardedHost = _context.req.headers['x-forwarded-host'];
    if (forwardedHost) {
        return forwardedHost !== environments.ADMIN_DOMAIN && forwardedHost !== environments.CLIENT_DOMAIN;
    }
    return _context.req.headers.host !== environments.CLIENT_DOMAIN && _context.req.headers.host !== environments.ADMIN_DOMAIN;
}

export function getRequestHost(_context: any) {
    const forwardedHost = _context.req.headers['x-forwarded-host'];
    if (forwardedHost) {
        return forwardedHost;
    }
    return _context.req.headers.host;
}

export function checkHasAdminDomain(host: string) {
    return host === environments.ADMIN_DOMAIN;
}

export function checkHasClientDomain(host: string) {
    return host === environments.CLIENT_DOMAIN;
}

export async function checkIfUserIsAuthorizedToViewPage(_context: any, workspace: WorkspaceDto) {
    const config = getServerSideAuthHeaderConfig(_context);

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
        if (!user?.roles?.includes('FORM_CREATOR') || !workspace.dashboardAccess) {
            return false;
        }
    } catch (e) {
        return false;
    }

    return true;
}

export function getServerSideAuthHeaderConfig(_context: any) {
    const { cookies } = _context.req;
    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';
    return {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };
}

export async function getServerSidePropsInClientHostWithWorkspaceName(_context: any) {
    const hasClientDomain = checkHasClientDomain(getRequestHost(_context));
    if (!hasClientDomain) {
        return {
            notFound: true
        };
    }
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    if (!globalProps.workspace?.id) {
        return {
            notFound: true
        };
    }
    return {
        props: {
            ...globalProps
        }
    };
}

export async function checkIfUserIsAuthorizedToViewWorkspaceSettingsPage(_context: any, workspace: WorkspaceDto) {
    const config = getServerSideAuthHeaderConfig(_context);

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
        if (!user?.roles?.includes('FORM_CREATOR') || !workspace.dashboardAccess || workspace.ownerId !== user.id) {
            return false;
        }
    } catch (e) {
        return false;
    }

    return true;
}
