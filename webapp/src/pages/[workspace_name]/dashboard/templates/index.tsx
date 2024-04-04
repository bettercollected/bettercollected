import React from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import TemplateSection from '@Components/Template/TemplateSection';

import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import environments from '@app/configs/environments';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useGetTemplatesQuery } from '@app/store/template/api';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import { useAppSelector } from '@app/store/hooks';
import { selectAuth } from '@app/store/auth/slice';

const TemplatePage = (props: any) => {
    const { t } = useTranslation();
    const { predefined_templates, workspace } = props;
    let p = [...predefined_templates];
    if (p.length > 7) {
        p = p.slice(0, 7);
    }

    const { data, isLoading } = useGetTemplatesQuery({
        workspace_id: workspace?.id
    }, { pollingInterval: 30000 });

    const auth = useAppSelector(selectAuth);
    const { data: v2Forms } = useGetTemplatesQuery({ workspace_id: workspace.id, v2: true });
    return (
        <SidebarLayout boxClassName=" h-full">
            <NextSeo title={t('TEMPLATE.TEMPLATES') + ' | ' + workspace.workspaceName} noindex={false}
                     nofollow={false} />
            {predefined_templates && Array.isArray(predefined_templates) && predefined_templates.length > 0 &&
                <TemplateSection title={t('TEMPLATE.DEFAULT')}  templates={p} className={'h-[400px]'} />}
            {auth?.roles?.includes('ADMIN') &&
                <TemplateSection title={t('TEMPLATE.YOUR_WORKSPACE') + " v2"} showButtons={false} templates={v2Forms} />
            }
            <TemplateSection title={t('TEMPLATE.YOUR_WORKSPACE') }  templates={data} />
        </SidebarLayout>
    );
};

export default TemplatePage;

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
