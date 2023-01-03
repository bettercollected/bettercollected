import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export function checkHasCustomDomain(_context: any) {
    return _context.req.headers.host !== environments.CLIENT_HOST;
}

export async function checkIfUserIsAuthorizedToViewPage(_context: any, workspace: WorkspaceDto) {
    const config = getServerSideAuthHeaderConfig(_context);

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.payload?.content ?? null;
        if (!user?.user?.roles?.includes('FORM_CREATOR') || user?.user?.id !== workspace.ownerId) {
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
