import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import environments from '@app/configs/environments';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export default async function getServerSideProps({ locale, ..._context }: any): Promise<{
    props: IServerSideProps;
}> {
    const host = _context.req.headers.host === 'localhost:3000' ? environments.WORKSPACE_ID : _context.req.headers.host;

    const hasCustomDomain = environments.IS_CUSTOM_DOMAIN || host !== 'bettercollected.sireto.dev';
    let workspaceId: string | null = null;
    let workspace: WorkspaceDto | null = null;

    try {
        if (hasCustomDomain) {
            const workspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces?custom_domain=${host}`).catch((e) => e);
            const wspace = (await workspaceResponse?.json().catch((e: any) => e)) ?? null;
            workspace = wspace;
            workspaceId = wspace.id;
        }
    } catch (e: any) {
        console.info(e.message());
    }

    if (hasCustomDomain && environments?.WORKSPACE_ID) workspaceId = environments.WORKSPACE_ID;

    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'de'])),
            hasCustomDomain,
            workspaceId,
            workspace
        }
    };
}
