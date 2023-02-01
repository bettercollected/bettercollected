import React, { useEffect, useRef, useState } from 'react';

import { useRouter } from 'next/router';

import { Widget } from '@typeform/embed-react';

import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import SingleFormPage from '@app/pages/forms/[id]';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default SingleFormPage;

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const hasCustomDomain = checkHasCustomDomain(_context);

    if (hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    const config = getServerSideAuthHeaderConfig(_context);

    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;

    if (!globalProps.workspace.id) {
        return {
            notFound: true
        };
    }
    let form: StandardFormDto | null = null;

    try {
        if (globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspace.id}/forms/${slug}`, config).catch((e) => e);
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
