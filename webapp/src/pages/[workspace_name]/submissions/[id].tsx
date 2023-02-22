import React from 'react';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import Submission from '@app/pages/submissions/[id]';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default Submission;

export async function getServerSideProps(_context: any) {
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

    let form: StandardFormDto | null = null;

    const submissionId = _context.query.id;

    const config = getServerSideAuthHeaderConfig(_context);

    try {
        if (globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/submissions/${submissionId}`, config).catch((e) => e);
            form = (await formResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
        }
    } catch (err) {
        form = null;
        console.error(err);
    }

    return {
        props: {
            ...globalProps,
            form,
            submissionId
        }
    };
}
