import React from 'react';

import { useRouter } from 'next/router';

import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import ContentLayout from '@app/layouts/_content-layout';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';

interface ISingleFormPage extends IServerSideProps {
    form: StandardFormDto;
    slug: string;
}

export default function SingleFormPage(props: any) {
    const { form, back } = props;

    const router = useRouter();

    if (!form) return <FullScreenLoader />;

    const responderUri = form.settings.embedUrl;
    return (
        <div className="relative">
            <div className="absolute overflow-hidden inset-0">
                <div className="absolute top-[60%] left-[-100px] w-[359px] h-[153px] bg-gradient-to-r from-orange-200 via-orange-300 to-orange-400 rotate-90 blur-dashboardBackground opacity-[20%]" />
                <div className="absolute top-[35%] left-[65%] w-[765px] h-[765px] bg-gradient-to-r from-cyan-300 via-sky-300 to-cyan-400 blur-dashboardBackground opacity-[15%]" />
                <div className="absolute bottom-0 left-[50%] w-[599px] h-[388px] bg-gradient-to-r from-rose-200 via-rose-300 to-rose-400 rotate-180 blur-dashboardBackground opacity-[20%]" />
            </div>
            {back && (
                <Button className="!absolute !top-0 !left-0 w-auto z-10 !h-8 mx-4 mt-0 sm:mt-1 md:mt-3 hover:!-translate-y-0 focus:-translate-y-0" variant="solid" onClick={() => router.push(`/${props.workspace.workspaceName}?view=forms`)}>
                    <LongArrowLeft width={15} height={15} />
                </Button>
            )}

            <ContentLayout className={'absolute left-0 !min-h-screen right-0 top-0 bottom-0 !p-0 !m-0'}>
                {!!responderUri && (
                    <iframe src={`${responderUri}?embedded=true`} width="100%" height="100%" frameBorder="0" marginHeight={0} marginWidth={0}>
                        <Loader />
                    </iframe>
                )}
            </ContentLayout>
        </div>
    );
}

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    let back = false;
    const query = _context.query;

    if (query?.back) {
        back = (query?.back && (query?.back === 'true' || query?.back === true)) ?? false;
    }

    const hasCustomDomain = _context.req.headers.host !== environments.CLIENT_HOST;

    if (hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
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
    return {
        props: {
            ...globalProps,
            form,
            slug,
            back
        }
    };
}
