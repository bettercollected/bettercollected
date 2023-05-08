import React from 'react';

import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import SingleFormPage from '@app/pages/forms/[id]';
import { checkHasClientDomain, getRequestHost } from '@app/utils/serverSidePropsUtils';

export default SingleFormPage;

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const hasClientDomain = checkHasClientDomain(getRequestHost(_context));
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
    return {
        props: {
            ...globalProps,
            slug,
            back
        }
    };
}
