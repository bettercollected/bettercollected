import React from 'react';

import { useRouter } from 'next/router';

import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import ContentLayout from '@app/layouts/_content-layout';
import globalServerProps from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';

interface ISingleFormPage extends IServerSideProps {
    form: StandardFormDto;
    slug: string;
}

export default function SingleFormPage({ form, ...props }: ISingleFormPage) {
    const router = useRouter();

    if (!form) return <FullScreenLoader />;

    const responderUri = form.settings.embedUrl;
    return (
        <div className="relative">
            <Button className="!absolute !top-0 !left-0 w-auto z-10 !h-8 mx-4 mt-0 sm:mt-1 md:mt-3 hover:!-translate-y-0 focus:-translate-y-0" variant="solid" onClick={() => router.push('/')}>
                <LongArrowLeft width={15} height={15} />
            </Button>

            <ContentLayout className={'absolute left-0 right-0 top-0 bottom-0 !p-0 !m-0'}>
                <iframe src={`${responderUri}?embedded=true`} width="100%" height="100%" frameBorder="0" marginHeight={0} marginWidth={0}>
                    <Loader />
                </iframe>
            </ContentLayout>
        </div>
    );
}

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    const query = _context.query;
    const globalProps = (await globalServerProps(_context)).props;
    let form: StandardFormDto | null = null;

    try {
        if (globalProps.hasCustomDomain && globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/forms/${slug}`).catch((e) => e);
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
            slug
        }
    };
}
