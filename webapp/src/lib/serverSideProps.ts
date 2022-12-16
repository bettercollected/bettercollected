import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import environments from '@app/configs/environments';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

export default async function getServerSideProps({ locale, ..._context }: any): Promise<{
    props: IServerSideProps;
}> {
    const hasCustomDomain = !!environments.IS_CUSTOM_DOMAIN;
    let workspaceId: string | null = null;
    if (hasCustomDomain && environments?.WORKSPACE_ID) workspaceId = environments.WORKSPACE_ID;

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
