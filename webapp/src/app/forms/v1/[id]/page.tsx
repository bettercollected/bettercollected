import React from 'react';
import { headers } from 'next/headers';
import { redirect, notFound } from 'next/navigation';
import environments from '@app/configs/environments';
import SingleFormPage from '@app/Components/Form/v1/SingleFormPage';
import { WorkspaceDispatcher } from '@app/app/[workspace_name]/_dispatcher/WorkspaceDispatcher';
import ReduxWrapperAppRouter from '@app/containers/ReduxWrapperAppRouter';

async function getWorkspaceByDomain(domain: string) {
    const workspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`, { next: { revalidate: 300 } });
    const workspace = await workspaceResponse.json();
    return workspace;
}

async function getForm(workspaceId: string, formId: string) {
    try {
        const formResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formId}`);
        const form = await formResponse.json();
        return form;
    } catch (error) {
        return null;
    }
}

export async function generateMetadata(props: { params: Promise<{ id: string }> }) {
    const params = await props.params;
    const host = (await headers()).get('x-forwarded-host') || (await headers()).get('host') || '';
    const workspace = await getWorkspaceByDomain(host);

    if (!workspace?.id) return {};

    const form = await getForm(workspace.id, params.id);
    const title = form?.title || workspace.title;

    return {
        title: title,
        description: form?.description || workspace.description,
        openGraph: {
            title: title,
            description: form?.description || workspace.description,
            images: [
                {
                    url: form?.coverImage || workspace.profileImage
                }
            ]
        }
    };
}

export default async function Page(
    props: { params: Promise<{ id: string }>; searchParams: Promise<{ [key: string]: string | string[] | undefined }> }
) {
    const searchParams = await props.searchParams;
    const params = await props.params;
    const host = (await headers()).get('x-forwarded-host') || (await headers()).get('host') || '';
    const hasCustomDomain = host !== environments.FORM_DOMAIN;

    if (!hasCustomDomain) {
        redirect('/');
    }

    const workspace = await getWorkspaceByDomain(host);

    if (!workspace?.id) {
        return notFound();
    }

    const form = await getForm(workspace.id, params.id);

    if (!form || !form.formId) {
        return notFound();
    }

    const back = searchParams.back === 'true';

    return (
        <ReduxWrapperAppRouter>
            <WorkspaceDispatcher workspace={workspace}>
                <SingleFormPage
                    workspace={workspace}
                    form={form}
                    slug={params.id}
                    hasCustomDomain={hasCustomDomain}
                    back={back}
                />
            </WorkspaceDispatcher>
        </ReduxWrapperAppRouter>
    );
}
