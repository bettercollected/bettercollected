import React from 'react';

import { NextSeo } from 'next-seo';

import LoadingIcon from '@Components/Common/Icons/Loading';
import TemplateSection from '@Components/Template/TemplateSection';

import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useGetTemplatesQuery } from '@app/store/template/api';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

const TemplatePage = (props: any) => {
    const { predefined_templates, workspace, notFound } = props;
    const { data, isLoading } = useGetTemplatesQuery(workspace?.id);
    const p = [...predefined_templates, ...predefined_templates, ...predefined_templates];
    return (
        <SidebarLayout boxClassName=" h-full">
            <NextSeo title={'Templates | ' + workspace.workspaceName} noindex={false} nofollow={false} />
            {predefined_templates && Array.isArray(predefined_templates) && predefined_templates.length > 0 && <TemplateSection title={'Default'} templates={predefined_templates} className={'h-[400px] overflow-hidden'} />}
            <TemplateSection title={'Your Workspace'} templates={data} />
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
