import React from 'react';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import SingleFormPage from '@app/pages/forms/[id]';
import { checkHasClientDomain } from '@app/utils/serverSidePropsUtils';

export default SingleFormPage;

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const hasClientDomain = checkHasClientDomain(_context);
    if (!hasClientDomain) {
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
    let form: StandardFormDto | null = null;

    try {
        if (globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspace.id}/forms/${slug}`).catch((e) => e);
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
