import React from 'react';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import SingleFormPage from '@app/pages/forms/[id]';
import { checkHasClientDomain, getRequestHost, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';


export default SingleFormPage;

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const hasClientDomain = checkHasClientDomain(getRequestHost(_context));
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;
    if (!hasClientDomain) {
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    }

    if (!globalProps.workspace?.id) {
        return {
            notFound: true
        };
    }
    let form = null;
    const config = getServerSideAuthHeaderConfig(_context);
    const { id } = _context.query;
    try {
        const formResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${globalProps.workspace?.id}/forms/${id}`, config);
        form = (await formResponse?.json().catch((e: any) => e)) ?? null;
        if (!form) {
            return {
                notFound: true
            };
        }
        return {
            props: {
                ...globalProps,
                slug,
                back,
                form
            }
        };
    } catch (err) {
        return {
            props: {
                ...globalProps,
                slug,
                back,
                error: true
            }
        };
    }
    // return {
    //     props: {
    //         ...globalProps,
    //         slug,
    //         back
    //     }
    // };
}