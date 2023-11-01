import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import TemplateSection from '@Components/Template/TemplateSection';

import { ChevronForward } from '@app/components/icons/chevron-forward';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import environments from '@app/configs/environments';
import Layout from '@app/layouts/_layout';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

const TemplateAllPages = (props: any) => {
    const { predefined_templates, workspace, notFound } = props;
    const { t } = useTranslation();
    const router = useRouter();
    if (notFound) {
        return <div>Not Found</div>;
    }
    const d = [...predefined_templates, ...predefined_templates, ...predefined_templates, ...predefined_templates];
    const handleClickBack = () => {
        router.back();
    };
    return (
        <Layout showNavbar className={'bg-white !px-0'}>
            <NextSeo title={t('TEMPLATE.ALL_TEMPLATES') + ' | ' + workspace.workspaceName} noindex={false} nofollow={false} />
            <div className="flex w-full items-center gap-1 px-5 pt-2 cursor-pointer" onClick={handleClickBack}>
                <ChevronForward className=" rotate-180 h-6 w-6 p-[2px] " />
                <p className={'text-sm text-black-700 font-normal'}>{t('BUTTON.BACK')}</p>
            </div>
            <div className={'flex flex-col mt-4 px-2 md:px-12'}>
                <h1 className={'text-xl font-semibold text-black-800'}>{t('TEMPLATE.ALL_TEMPLATES')}</h1>
                <TemplateSection templates={d} className={'md:pl-[130px] md:pr:[80px]'} />
            </div>
        </Layout>
    );
};

export default TemplateAllPages;

export async function getServerSideProps(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);
    if (!props.props) {
        return props;
    }
    const globalProps = props.props;
    const config = getServerSideAuthHeaderConfig(_context);
    try {
        const predefined_templates_response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/templates`, config);
        const predefined_templates = (await predefined_templates_response?.json().catch((e: any) => e)) ?? null;
        if (!predefined_templates) {
            return {
                notFound: true
            };
        }
        return {
            props: {
                predefined_templates,
                ...globalProps
            }
        };
    } catch (e) {
        return {
            props: {
                error: true
            }
        };
    }
}
