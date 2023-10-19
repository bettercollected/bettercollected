import React from 'react';

import LoadingIcon from '@Components/Common/Icons/Loading';
import TemplateSection from '@Components/Template/TemplateSection';

import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import environments from '@app/configs/environments';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useGetTemplatesQuery } from '@app/store/template/api';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

const TemplatePage = (props: any) => {
    const { predefined_templates, workspace, notFound } = props;
    console.log('predefined', predefined_templates);
    const { data, isLoading } = useGetTemplatesQuery(workspace?.id);
    console.log('workspace_template', data);
    if (isLoading) {
        return <LoadingIcon />;
    }
    const p = [...predefined_templates, ...predefined_templates, ...predefined_templates];
    return (
        <SidebarLayout boxClassName=" h-full">
            <TemplateSection title={'Default'} templates={p} className={'h-[400px] overflow-hidden'} />
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
