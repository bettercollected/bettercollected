import React from 'react';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import SingleFormPage from '@app/pages/[workspace_name]/forms/[id]';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default SingleFormPage;

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const config = getServerSideAuthHeaderConfig(_context);

    const hasCustomDomain = checkHasCustomDomain(_context);

    if (!hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    let form: StandardFormDto | null = null;

    try {
        if (globalProps.hasCustomDomain && globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspace?.id}/forms/${slug}`, config).catch((e) => e);
            form = (await formResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
        }
    } catch (err) {
        form = null;
        console.error(err);
    }

    if (!form) {
        return {
            notFound: true
        };
    }

    return {
        props: {
            ...globalProps,
            form,
            slug,
            back
        }
    };
}
