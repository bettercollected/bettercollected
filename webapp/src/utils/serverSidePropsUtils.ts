import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export function checkHasCustomDomain(_context: any) {
    return _context.req.headers.host !== environments.CLIENT_HOST && _context.req.headers.host !== environments.ADMIN_HOST;
}

export function checkHasAdminDomain(_context: any) {
    return _context.req.headers.host === environments.ADMIN_HOST;
}

export function checkHasClientDomain(_context: any) {
    return _context.req.headers.host === environments.CLIENT_HOST;
}

export async function checkIfUserIsAuthorizedToViewPage(_context: any, workspace: WorkspaceDto) {
    const config = getServerSideAuthHeaderConfig(_context);

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.user ?? null;
        if (!user?.roles?.includes('FORM_CREATOR') || user?.id !== workspace.ownerId) {
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
    const hasClientDomain = checkHasClientDomain(_context);
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
