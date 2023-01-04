import React from 'react';

import { useRouter } from 'next/router';

import BreadcrumbRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface ISubmission extends IServerSideProps {
    form: StandardFormDto;
}

export default function Submission({ workspace, submissionId }: ISubmission) {
    const router = useRouter();
    const breakpoint = useBreakpoint();
    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const form: any = data?.payload?.content ?? [];

    if (isLoading || isError || !data) return <FullScreenLoader />;

    const goToSubmissions = () => {
        router
            .push(
                {
                    pathname: `/${router.query.workspace_name}`,
                    query: { view: 'mySubmissions' }
                },
                undefined,
                { scroll: false, shallow: true }
            )
            .then((r) => r)
            .catch((e) => e);
    };

    const breadcrumbsItem = [
        {
            title: 'Home',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: () => router.push(`/${router.query.workspace_name}`, undefined, { scroll: false, shallow: true })
        },
        {
            title: 'Submissions',
            onClick: goToSubmissions
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.formId, 10) : form.formId,
            icon: ''
        }
    ];

    return (
        <div className="relative container mx-auto px-6 md:px-0">
            <BreadcrumbRenderer breadcrumbsItem={breadcrumbsItem} />
            <FormRenderer form={form} />
        </div>
    );
}

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

    try {
        if (globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/submissions/${submissionId}`, getServerSideAuthHeaderConfig(_context)).catch((e) => e);
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
