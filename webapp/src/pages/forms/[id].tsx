import React from 'react';

import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import { useRouter } from 'next/router';

import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import ContentLayout from '@app/layouts/_content-layout';
import { CompanyJsonDto } from '@app/models/dtos/customDomain';
import { GoogleFormDto } from '@app/models/dtos/googleForm';

interface ISingleFormPage {
    form: GoogleFormDto | null;
}

export default function SingleFormPage(props: ISingleFormPage) {
    const form: GoogleFormDto | null = props?.form;
    const router = useRouter();

    if (!form) return <FullScreenLoader />;

    const responderUri = form.responderUri;
    return (
        <>
            <Button className="w-auto z-10 !h-8 mx-4 mt-0 sm:mt-1 md:mt-3 hover:!-translate-y-0 focus:-translate-y-0" variant="solid" onClick={() => router.push('/')}>
                <LongArrowLeft width={15} height={15} />
            </Button>
            <ContentLayout className={'absolute left-0 right-0 top-0 bottom-0 !py-0 !px-0'}>
                <iframe src={`${responderUri}?embedded=true`} width="100%" height="100%" frameBorder="0" marginHeight={0} marginWidth={0}>
                    <Loader />
                </iframe>
            </ContentLayout>
        </>
    );
}

export async function getServerSideProps(_context: any) {
    const slug = _context.params.id;
    const hasCustomDomain = !!environments.IS_CUSTOM_DOMAIN;
    let companyJson: CompanyJsonDto | null = null;
    let forms: Array<GoogleFormDto> = [];

    try {
        if (hasCustomDomain && !!environments.CUSTOM_DOMAIN_JSON) {
            const json = await fetch(environments.CUSTOM_DOMAIN_JSON).catch((e) => e);
            companyJson = (await json.json().catch((e: any) => e)) ?? null;
            if (companyJson?.forms) forms = [...companyJson?.forms];
        }
    } catch (err) {
        companyJson = null;
        console.error(err);
    }

    const filteredForm = forms.filter((form) => form.info.title.toLowerCase().replaceAll(' ', '-') === slug);
    let form: GoogleFormDto | null = null;
    if (filteredForm.length > 0) form = filteredForm[0];

    return {
        props: {
            ...(await serverSideTranslations(_context.locale, ['common'], null, ['en', 'de'])),
            form,
            companyJson,
            hasCustomDomain
        }
    };
}
